import os

from jinja2 import Environment, FileSystemLoader, Template
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from core.utils import var_or_exception

GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
OPENAI_KEY_VAR = "OPENAI_API_KEY"


def google_model(model_name: str) -> Model:
  key = var_or_exception(GOOGLE_API_KEY_VAR)
  provider = GoogleProvider(api_key=key)
  return GoogleModel(model_name, provider=provider)


def gemini_2_5_flash_lite() -> Model:
  return google_model("gemini-2.5-flash-lite-preview-09-2025")


def gemini_2_5_flash() -> Model:
  return google_model("gemini-2.5-flash-preview-09-2025")


def gemini_2_5_settings(budget: int) -> ModelSettings:
  return GoogleModelSettings(google_thinking_config={
    "include_thoughts": True,
    "thinking_budget": budget
  })


def openai_model(model_name: str) -> Model:
  key = var_or_exception(OPENAI_KEY_VAR)
  provider = OpenAIProvider(api_key=key)
  return OpenAIResponsesModel(model_name, provider=provider)


def gpt_5_nano() -> Model:
  return openai_model("gpt-5-nano-2025-08-07")


class TemplateManager:
  
  def __init__(self, tpl_dir: str | None = None) -> None:
    if tpl_dir is None:
      tpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    
    self._env = Environment(
      loader=FileSystemLoader(tpl_dir), 
      auto_reload=True
    )
    
  def get_template(self, name) -> Template:
    if not name.endswith(".jinja"):
      name += ".jinja"  
    
    return self._env.get_template(name)
  
  def render(self, name: str, context: dict) -> str:
    tpl = self.get_template(name)
    return tpl.render(context)
