import logging
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models import Model

from core.agents.common import TemplateManager
from db.repositories.helpers import TextVideoData


class TopicName(BaseModel):
  id: UUID
  name: str


class AdditionalTopic(BaseModel):
  id: UUID
  name: str
  confidence: float
  reason: str

  class Config:  # type: ignore
    extra = "forbid"


class MainTopic(BaseModel):
  id: UUID
  name: str
  confidence: float
  reason: str
  additional: list[AdditionalTopic]

  class Config:  # type: ignore
    extra = "forbid"


class TopicAgentResponse(BaseModel):
  topics: list[MainTopic]

  class Config:  # type: ignore
    extra = "forbid"


class TopicAgent:

  def __init__(self, model: Model, model_settings: ModelSettings, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.topic_agent")
    self._tpl_mgr = tpl_mgr

    agent = Agent(
      model,
      model_settings=model_settings,
      instructions=self._tpl_mgr.render("topic_system", {}),
      output_type=TopicAgentResponse
    )
    self._agent = agent

  async def run(self, video: TextVideoData, topics: list[TopicName], temperature: float = 0) -> TopicAgentResponse:
    user_prompt = self._tpl_mgr.render("topic_user", {
      "topics": [t.model_dump(mode="json") for t in topics],
      "video": video.model_dump(mode="json")
    })

    res = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=temperature)
    )

    usage = res.usage()
    self._log.debug(
      f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
    )

    return res.output
