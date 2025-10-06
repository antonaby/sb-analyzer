from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from core.agents.video import FrameContent, VideoAnalyzer
from core.agents.transcribe import AudioAnalyzer
from core.utils import var_or_exception


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


@dataclass
class SummaryAgentDeps:
  video: VideoAnalyzer
  audio: AudioAnalyzer
  

class SummaryAgent:
  
  def __init__(self, model_name = GOOGLE_DEFAULT_MODEL):
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      deps_type=SummaryAgentDeps
    )
    
    @agent.tool
    async def get_frame_content(ctx: RunContext[SummaryAgentDeps], time_in_seconds: float) -> FrameContent:
      """
      Retrieves the content/description of a video frame at a specific time.

      Args:
        time_in_seconds (float): The time position in the video (in seconds).
          Fractions of a second are allowed (e.g., 7.9).
      """
      return await ctx.deps.video.get_frame_content(time_in_seconds)
    
    self._agent = agent
    
  async def summary(self, video: VideoAnalyzer, audio: AudioAnalyzer):
    pass
