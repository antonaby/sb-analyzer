import asyncio
from dataclasses import dataclass
import logging
from typing import Optional, TypedDict
from uuid import UUID
from openai import BaseModel
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from core.agents.common import TopicDetails, TopicLoader
from core.agents.tpl import TemplateManager
from core.video import Frame, VideoData
from core.transcribe import AudioData
from models.common import PostDetails
from core.utils import var_or_exception


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


@dataclass
class SummaryAgentDeps:
  video: VideoData
  audio: AudioData
  topic_loader: TopicLoader


class TopicProposal(BaseModel):
  id: Optional[UUID]
  name: str
  confidence: float
  
  class Config: # type: ignore
    extra = "forbid"
  

class VideoSummary(BaseModel):
  label: str
  synopsis: str
  actions: list[str]
  topics: list[TopicProposal]
  
  class Config: # type: ignore
    extra = "forbid"


class VideoMetadata(TypedDict):
  post_from: str
  title: str
  description: str
  hashtags: list[str]
  duration: float
  uploaded_at_iso: str
  likes: int
  views: int
  comments: int


class UserPromptInput(TypedDict):
  metadata: VideoMetadata
  frames: list[dict]
  transcriptions: list[dict]


class SummaryAgent:
  
  def __init__(self, tpl_mgr: TemplateManager, topic_loader: TopicLoader, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.videosummary")
    self._tpl_mgr = tpl_mgr
    self._topic_loader = topic_loader
    
    self._create_agent(model_name)
  
  def _create_agent(self, model_name: str):
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("summary_system_ext", {}),
      deps_type=SummaryAgentDeps,
      output_type=VideoSummary
    )
    
    @agent.tool
    async def get_frame(ctx: RunContext[SummaryAgentDeps], time_sec: float) -> Frame:
      """
      Retrieves a video frame analysis at a specific time.

      Args:
        time_sec (float): The time position in the video (in seconds).
          Fractions of a second are allowed (e.g., 7.9).
      Returns:
        Frame: a fame analysis at the provided time
      """
      return await ctx.deps.video.get_frame(time_sec)
    
    @agent.tool
    async def search_topics(ctx: RunContext[SummaryAgentDeps], search_keywords: list[str]) -> list[TopicDetails]:
      """
      Retrieves a list of topics based on the provided search keywords.

      Args:
        search_keywords (list[str]): A list of keywords used to search for matching topics.
          Each keyword is compared against the topic's name using full-text search.
          Each element can include multiple words combined with '&' for AND logic.
          Multiple elements are combined with OR logic across the list.

          For example:
            ["One & Two", "Three"]
          searches for topics that match:
            ("One" AND "Two") OR ("Three")

      Returns:
        list[TopicDetails]: A list of topic details (ID and name) matching the search query.
          The returned topics are ordered by descending relevance - topics whose names
          more closely match the search terms appear first.
      """
      return await ctx.deps.topic_loader.search_topics(search_keywords)
    
    self._agent = agent

  async def run(self, post: PostDetails, video: VideoData, audio: AudioData) -> VideoSummary:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(),
      audio.get_transcription()
    )
    
    input: UserPromptInput = {
      "metadata": {
        "post_from": post.get("post_from", "tiktok"),
        "title": post.get("text", "no title"),
        "description": post.get("description", "no description"),
        "hashtags": post.get("hashtags", []),
        "duration": video.get_duration(),
        "uploaded_at_iso": post.get("uploaded_at_iso", "unknown"),
        "likes": post.get("likes", 0),
        "views": post.get("views", 0),
        "comments": post.get("comments", 0)
      },
      "frames": [f.model_dump() for f in basic_frames],
      "transcriptions": [t.model_dump() for t in transcription]
    }
    
    user_prompt = self._tpl_mgr.render("summary_user", {"input": input})
    res = await self._agent.run(
      user_prompt,
      deps=SummaryAgentDeps(video=video, audio=audio, topic_loader=self._topic_loader),
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
