import logging
from typing import List, Literal, Optional, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from core.agents.tpl import TemplateManager
from core.utils import var_or_exception
from models.common import VideoData


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


class SupportingVideo(BaseModel):
  video_id: UUID
  evidence: str

class AlternateConsidered(BaseModel):
  topic_id: UUID
  similarity_hint: str

class TopicDecision(BaseModel):
  canonical_topic: str
  decision: Literal["existing", "new"]
  topic_id: Optional[UUID]
  proposed_topic_name: Optional[str]
  supporting_videos: List[SupportingVideo]
  alternates_considered: Optional[List[AlternateConsidered]] = Field(default_factory=list)
  confidence: float

class TopicsResponse(BaseModel):
  topics: List[TopicDecision]


class UserPromptInput(TypedDict):
  videos: list[VideoData]


class VideoSeriesAgent:

  def __init__(self, tpl_mgr: TemplateManager, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.authoranalyzer")
    self._tpl_mgr = tpl_mgr
    
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("series_system", {}),
      output_type=TopicsResponse
    )
    self._agent = agent
    
  async def run(self, video_data: list[VideoData]) -> TopicsResponse:
    input: UserPromptInput = {
      "videos": video_data
    }
    
    user_prompt = self._tpl_mgr.render("series_user", {"input": input})
    run = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = run.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return run.output
  