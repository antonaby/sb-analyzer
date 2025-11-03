import asyncio
import logging
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from openai import BaseModel
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.common import TemplateManager, TopicName, VideoMetadata
from core.processors.common import PostDetails
from core.transcribe import FileAudioData
from core.video import FileVideoData
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import TextVideoData


class ChallengeGenAgentRun(BaseModel):
  video: TextVideoData
  pattern_group_id: UUID

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeProposal(BaseModel):
  id: UUID | None
  name: str
  pattern: str

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeGenAgentResponse(BaseModel):
  existing: list[ChallengeProposal]
  new: list[ChallengeProposal]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeData(BaseModel):
  id: UUID
  name: str
  pattern: str


class ChallengeLoader:

  def __init__(self, db: async_sessionmaker[AsyncSession]):
    self._db = db

  async def load_patterns(self, pattern_group_id: UUID) -> list[str]:
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      patterns = await challenge_repo.get_challenge_patterns(pattern_group_id)
      return [f"{p.value} {p.example}" for p in patterns]

  async def search_challenges(self, pattern_group_id: UUID, keywords: list[str]) -> list[ChallengeData]:
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenges = await challenge_repo.search_challenges(pattern_group_id, keywords)
      return [ChallengeData(id=c.id, name=c.name, pattern=c.pattern_used) for c in challenges]


@dataclass
class ChallengeAgentDeps:
  pattern_group_id: UUID
  challenge_loader: ChallengeLoader


class ChallengeGenAgent:

  def __init__(self, model: Model, model_settings: ModelSettings, challenge_loader: ChallengeLoader, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.challenge_gen_agent")
    self._tpl_mgr = tpl_mgr
    self._challenge_loader = challenge_loader

    agent = Agent(
      model,
      model_settings=model_settings,
      instructions=self._tpl_mgr.render("challenge_gen_system", {}),
      output_type=ChallengeGenAgentResponse,
      deps_type=ChallengeAgentDeps
    )
    self._agent = agent

    @agent.tool
    async def search_challenges(ctx: RunContext[ChallengeAgentDeps], keywords: list[str]) -> list[ChallengeData]:
      """
      Retrieves a list of existing challenges that contain the keywords in the name.

      Args:
        keywords (list[str]): a list of keywords to search.
      """

      result = await ctx.deps.challenge_loader.search_challenges(ctx.deps.pattern_group_id, keywords)
      return result

  async def run(self, run: ChallengeGenAgentRun, temperature: float = 0.0) -> ChallengeGenAgentResponse:
    patterns = await self._challenge_loader.load_patterns(run.pattern_group_id)

    user_prompt = self._tpl_mgr.render("challenge_gen_user", {
      "patterns": patterns,
      "video": run.video.model_dump(mode="json", exclude_none=True)
    })

    res = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=temperature),
      deps=ChallengeAgentDeps(pattern_group_id=run.pattern_group_id, challenge_loader=self._challenge_loader)
    )

    usage = res.usage()
    self._log.debug(
      f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
    )

    return res.output


class ChallengeDifficultyPart(BaseModel):
  name: str
  value: float

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeDifficulty(BaseModel):
  total: float
  parts: list[ChallengeDifficultyPart]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeCategoryAgentResponse(BaseModel):
  topics: list[TopicName]
  difficulty: ChallengeDifficulty

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeCategoryAgentRun(BaseModel):
  challenge: str
  topics: list[TopicName]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeCategoryAgent:

  def __init__(self, model: Model, model_settings: ModelSettings, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.challenge_category_agent")
    self._tpl_mgr = tpl_mgr

    agent = Agent(
      model,
      model_settings=model_settings,
      instructions=self._tpl_mgr.render("challenge_category_system", {}),
      output_type=ChallengeCategoryAgentResponse,
    )
    self._agent = agent

  async def run(self, run: ChallengeCategoryAgentRun, temperature: float = 0.0) -> ChallengeCategoryAgentResponse:
    user_prompt = self._tpl_mgr.render("challenge_category_user", {
      "challenge": run.challenge,
      "topics": [t.model_dump(mode="json") for t in run.topics],
    })

    res = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=temperature),
    )

    usage = res.usage()
    self._log.debug(
      f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
    )

    return res.output


class ChallengeVideoAnalyzerRun(BaseModel):
  challenge: str
  max_frames: int
  post: PostDetails


class ChallengeVideoAnalyzerResponse(BaseModel):
  accuracy: float
  reason: str

  class Config:
    extra = "forbid"


class UserPromptInput(TypedDict):
  challenge: str
  metadata: VideoMetadata
  frames: list[dict]
  transcriptions: list[dict]


class ChallengeVideoAnalyzer:

  def __init__(self, model: Model, model_settings: ModelSettings, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.challenge_video_analyzer_agent")
    self._tpl_mgr = tpl_mgr

    agent = Agent(
      model,
      model_settings=model_settings,
      instructions=self._tpl_mgr.render("challenge_video_analyzer_system", {}),
      output_type=ChallengeVideoAnalyzerResponse,
    )
    self._agent = agent

  async def run(self, run: ChallengeVideoAnalyzerRun, video: FileVideoData, audio: FileAudioData, temperature: float = 0.0) -> ChallengeVideoAnalyzerResponse:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(frame_n=run.max_frames),
      audio.get_transcription()
    )

    post = run.post
    user_input: UserPromptInput = {
      "challenge": run.challenge,
      "metadata": {
        "post_from": post.post_from.value,
        "title": post.title,
        "description": post.description,
        "hashtags": post.hashtags,
        "duration": video.get_duration(),
        "uploaded_at_iso": post.uploaded_at.isoformat(),
        "likes": post.likes,
        "views": post.views,
        "comments": post.comments
      },
      "frames": [f.model_dump() for f in basic_frames],
      "transcriptions": [t.model_dump() for t in transcription]
    }

    user_prompt = self._tpl_mgr.render("only_input", {"input": user_input})
    res = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=temperature)
    )

    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")

    return res.output
