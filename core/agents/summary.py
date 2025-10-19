import asyncio
import logging
from dataclasses import dataclass
from typing import TypedDict

from openai import BaseModel
from pydantic_ai import Agent, RunContext, Tool, ModelSettings
from pydantic_ai.models import Model

from core.agents.common import TemplateManager
from core.transcribe import AudioData
from core.video import Frame, VideoData
from models.common import PostDetails


@dataclass
class SummaryAgentDeps:
  video: VideoData
  audio: AudioData


class FrameDetails(BaseModel):
  time_sec: float
  requested: bool

  class Config: # type: ignore
    extra = "forbid"


class VideoSummary(BaseModel):
  label: str
  synopsis: str
  actions: list[str]
  topics: list[str]
  frames: list[FrameDetails]
  
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
  
  def __init__(self, model: Model, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.video_summary")
    self._tpl_mgr = tpl_mgr
    
    self._create_agent(model)
  
  def _create_agent(self, model: Model):
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("summary_system", {}),
      deps_type=SummaryAgentDeps,
      output_type=VideoSummary
    )
    self._agent = agent
    
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

  async def run(self, post: PostDetails, video: VideoData, audio: AudioData, temperature: float = 0.0) -> VideoSummary:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(),
      audio.get_transcription()
    )
    
    user_input: UserPromptInput = {
      "metadata": {
        "post_from": post.get("post_from", "tiktok"),
        "title": post.get("title", "no title"),
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
    
    user_prompt = self._tpl_mgr.render("only_input", {"input": user_input})
    res = await self._agent.run(
      user_prompt,
      deps=SummaryAgentDeps(video=video, audio=audio),
      model_settings=ModelSettings(temperature=temperature)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
