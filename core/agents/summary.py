import asyncio
from dataclasses import dataclass
import logging
from typing import TypedDict, cast
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from core.agents.tpl import TemplateManager
from core.video import Frame, VideoData
from core.transcribe import AudioData
from models.common import PostDetails, VideoSummary
from core.utils import var_or_exception


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


@dataclass
class SummaryAgentDeps:
  video: VideoData
  audio: AudioData
  

class UserPromptContext(TypedDict):
  post_from: str
  title: str
  hashtags: list[str]
  duration: float
  frames: list[dict]
  transcriptions: list[dict]


class SummaryAgent:
  
  def __init__(self, tpl_mgr: TemplateManager, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.videosummary")
    self._tpl_mgr = tpl_mgr
    
    self._create_agent(model_name)
  
  def _create_agent(self, model_name: str):
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("summary_system", {}),
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
      """
      return await ctx.deps.video.get_frame(time_sec)
    
    self._agent = agent

  async def summary(self, post: PostDetails, video: VideoData, audio: AudioData) -> VideoSummary:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(),
      audio.get_transcription()
    )
    
    context: UserPromptContext = {
      "post_from": post.get("post_from", "tiktok"),
      "title": post.get("text", "no title"),
      "hashtags": post.get("hashtags", []),
      "duration": video.get_duration(),
      "frames": [f.model_dump() for f in basic_frames],
      "transcriptions": [t.model_dump() for t in transcription]
    }
    
    user_prompt = self._tpl_mgr.render("summary_user", cast(dict, context))
    res = await self._agent.run(
      user_prompt,
      deps=SummaryAgentDeps(video=video, audio=audio),
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
