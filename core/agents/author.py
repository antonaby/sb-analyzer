import logging
import os
from typing import TypedDict

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from core.utils import var_or_exception
from db.repositories.videos import VideoDataLoader, VideoData
from models.common import AuthorSummary


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


SYSTEM_PROMPT = """
  You are an assistant that analyzes primary author topics.
"""


class UserPromptContext(TypedDict):
  videos: list[VideoData]


class AuthorAnalyzer:

  def __init__(self, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.authoranalyzer")
    
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=SYSTEM_PROMPT,
      output_type=AuthorSummary
    )
    self._agent = agent
    
    self._load_template()
    
  def _load_template(self):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    self._user_prompt = env.get_template("author_tmp.jinja")
    
  async def analyze(self, data_loader: VideoDataLoader) -> AuthorSummary:
    video_data = await data_loader.load_video_data()
    
    context: UserPromptContext = {
      "videos": video_data
    }
    
    user_prompt = self._user_prompt.render(context)
    run = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = run.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return run.output
  