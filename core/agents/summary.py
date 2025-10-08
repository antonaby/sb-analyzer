import asyncio
from dataclasses import dataclass
import logging
import os
from typing import TypedDict
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from core.agents.video import Frame, VideoData
from core.agents.transcribe import AudioData
from core.models.common import PostDetails, VideoSummary
from core.utils import var_or_exception


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


SYSTEM_PROMPT_SUMMARY = """
  You are an assistant that analyzes structured video frame descriptions and audio transcription to infer the main idea of the entire video. 
  You will be given instructions on the output format, what to caption, and how to perform your job. 
  Follow those instructions.
"""

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
  
  def __init__(self, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.videosummary")
    self._load_template()
    self._create_agent(model_name)
  
  def _create_agent(self, model_name: str):
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=SYSTEM_PROMPT_SUMMARY,
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
  
  def _load_template(self):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    self._user_prompt = env.get_template("summary_tmp.jinja")
    
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
    
    user_prompt = self._user_prompt.render(context)
    res = await self._agent.run(
      user_prompt,
      deps=SummaryAgentDeps(video=video, audio=audio),
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
