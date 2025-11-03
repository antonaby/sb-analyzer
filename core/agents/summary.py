import asyncio
import logging
from dataclasses import dataclass
from typing import TypedDict

from openai import BaseModel
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models import Model

from core.agents.common import TemplateManager, VideoMetadata
from core.processors.common import PostDetails
from core.transcribe import FileAudioData
from core.video import Frame, FileVideoData


@dataclass
class SummaryAgentDeps:
  video: FileVideoData
  audio: FileAudioData


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

  async def run(self, post: PostDetails, video: FileVideoData, audio: FileAudioData, temperature: float = 0.0) -> VideoSummary:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(),
      audio.get_transcription()
    )
    
    user_input: UserPromptInput = {
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
      deps=SummaryAgentDeps(video=video, audio=audio),
      model_settings=ModelSettings(temperature=temperature)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
