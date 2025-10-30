from datetime import timezone, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun, ChallengeGenAgentResponse, \
  ChallengeCategoryAgent, ChallengeCategoryAgentRun, ChallengeCategoryAgentResponse
from core.agents.common import TopicName
from core.processors.common import JobProcessor
from db.models import Video, Challenge
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import full_video_data, TextVideoData
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository
from models.videos import ChallengeGenSpec, ChallengeCategorizationSpec


class ChallengeDetails(BaseModel):
  id: UUID
  name: str
  is_new: bool


class ChallengeProcessorResult(BaseModel):
  challenges: list[ChallengeDetails]


class ChallengeProcessorError(Exception):
  pass


class ChallengeProcessor(JobProcessor):

  def __init__(self, challenge_agent: ChallengeGenAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._challenge_agent = challenge_agent

  async def run(self, spec: ChallengeGenSpec) -> ChallengeProcessorResult:
    try:
      video, video_data = await self._get_video_data(spec.video_id)

      run_input = ChallengeGenAgentRun(video=video_data, pattern_group_id=spec.pattern_group_id)
      agent_response = await self._challenge_agent.run(run_input)

      result = await self._save_challenges(video, spec, agent_response)
      return result
    except Exception as e:
      await self._set_challenges_creating_error(spec.video_id)
      raise e

  async def _get_video_data(self, video_id: UUID) -> tuple[Video, TextVideoData]:

    async with self._db() as session:
      video_repo = VideoRepository(session)
      video = await video_repo.get_video_by_id(
        video_id,
        with_meta=True, with_annotations=True
      )

      video_data = full_video_data(video)
      return video, video_data

  async def _set_challenges_creating_error(self, video_id: UUID):
    async with self._db() as session:
      video_repo = VideoRepository(session)
      await video_repo.set_challenge_creating(video_id, True)
      await session.commit()

  async def _save_challenges(self, video: Video, spec: ChallengeGenSpec, agent_response: ChallengeGenAgentResponse) -> ChallengeProcessorResult:
    total_challenges: list[ChallengeDetails] = []
    async with self._db() as session:
      video = await session.merge(video, load=False)
      video.challenges_created_at = datetime.now(timezone.utc)
      video.challenges_creating_error = False

      challenge_repo = ChallengeRepository(session)
      await challenge_repo.unassign_videos(spec.pattern_group_id, spec.video_id)

      for c in agent_response.new:
        challenge_model = await challenge_repo.create_challenge(
          group_id=spec.pattern_group_id, name=c.name, pattern_used=c.pattern
        )
        total_challenges.append(
          ChallengeDetails(id=challenge_model.id, name=challenge_model.name, is_new=True)
        )

      for c in agent_response.existing:
        challenge_model = await challenge_repo.get_challenge(c.id) if c.id is not None else None
        if challenge_model is not None:
          total_challenges.append(
            ChallengeDetails(id=challenge_model.id, name=challenge_model.name, is_new=False)
          )

      for c in total_challenges:
        await challenge_repo.add_video(c.id, spec.video_id)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=total_challenges
    )


class ChallengeCategoryProcessorResult(BaseModel):
  topics: list[TopicName]
  difficulty: float


class ChallengeCategoryProcessor(JobProcessor):

  def __init__(self, challenge_cat_agent: ChallengeCategoryAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._agent = challenge_cat_agent

  async def run(self, spec: ChallengeCategorizationSpec) -> ChallengeCategoryProcessorResult:
    try:
      challenge, topics = await self._get_challenge(spec.challenge_id, spec.topic_group_id)

      run_input = ChallengeCategoryAgentRun(challenge=challenge.name, topics=topics)
      agent_response = await self._agent.run(run_input)

      result = await self._save_categories(challenge, agent_response)

      return result
    except Exception as e:
      await self._set_challenges_categorization_error(spec.challenge_id)
      raise e

  async def _set_challenges_categorization_error(self, challenge_id: UUID):
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      await challenge_repo.set_challenge_categorization(challenge_id, True)
      await session.commit()

  async def _get_challenge(self, challenge_id: UUID, topic_group_id: UUID) -> tuple[Challenge, list[TopicName]]:
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(challenge_id)
      if not challenge:
        raise ChallengeProcessorError(f"Challenge {challenge_id} not found")

      topic_repo = TopicRepository(session)
      all_topics = await topic_repo.get_all_topics(topic_group_id)
      topic_names = [TopicName(id=t.id, name=t.name) for t in all_topics]

      return challenge, topic_names

  async def _save_categories(self,
                             challenge: Challenge,
                             agent_response: ChallengeCategoryAgentResponse) -> ChallengeCategoryProcessorResult:
    async with self._db() as session:
      challenge = await session.merge(challenge, load=False)
      challenge.categorization_error = False
      challenge.categorized_at = datetime.now(timezone.utc)
      challenge.difficulty = agent_response.difficulty.total

      challenge_repo = ChallengeRepository(session)
      await challenge_repo.delete_old_topics(challenge.id)

      for topic in agent_response.topics:
        await challenge_repo.add_topic(challenge.id, topic.id)

      await session.commit()

    return ChallengeCategoryProcessorResult(
      topics=agent_response.topics,
      difficulty=agent_response.difficulty.total
    )
