import logging

from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models import Model

from core.agents.common import TemplateManager


class Translation(BaseModel):
  lang: str
  text: str


class TranslationAgentResponse(BaseModel):
  translations: list[Translation]


class TranslationAgentRun(BaseModel):
  languages: list[str]
  input: Translation


class TranslationAgent:

  def __init__(self, model: Model, tpl_mgr: TemplateManager):
    self._log = logging.getLogger("app.translation_agent")
    self._tpl_mgr = tpl_mgr

    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("translate_system", {}),
      output_type=TranslationAgentResponse
    )
    self._agent = agent

  async def run(self, run: TranslationAgentRun, temperature: float = 0.0) -> TranslationAgentResponse:
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