import logging
from uuid import UUID

from openai import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models import Model

from core.agents.common import TemplateManager
from db.repositories.helpers import TextVideoData


class ChallengeGenAgentRun(BaseModel):
  topic: str
  languages: list[str]
  videos: list[TextVideoData]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeName(BaseModel):
  lang: str
  name: str

  class Config:  # type: ignore
    extra = "forbid"


class VideoChallenge(BaseModel):
  id: UUID
  reason: str

  class Config:  # type: ignore
    extra = "forbid"


class Challenge(BaseModel):
  translations: list[ChallengeName]
  videos: list[VideoChallenge]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeGenAgentResponse(BaseModel):
  challenges: list[Challenge]

  class Config:  # type: ignore
    extra = "forbid"


class ChallengeGenAgent:

  def __init__(self, model: Model, model_settings: ModelSettings, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.challenge_gen_agent")
    self._tpl_mgr = tpl_mgr

    agent = Agent(
      model,
      model_settings=model_settings,
      instructions=self._tpl_mgr.render("challenge_gen_system", {}),
      output_type=ChallengeGenAgentResponse
    )
    self._agent = agent

  async def run(self, run: ChallengeGenAgentRun, temperature: float = 0.1) -> ChallengeGenAgentResponse:
    user_prompt = self._tpl_mgr.render("only_input", {"input": run.model_dump(mode="json")})

    res = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=temperature)
    )

    usage = res.usage()
    self._log.debug(
      f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
    )

    return res.output
