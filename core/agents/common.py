from dataclasses import dataclass
import logging
import os
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from jinja2 import Environment, FileSystemLoader, Template
from core.utils import var_or_exception
from db.repositories.topics import TopicRepository


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"


def google_model(model_name: str) -> Model:
  key = var_or_exception(GOOGLE_API_KEY_VAR)
  provider = GoogleProvider(api_key=key)
  return GoogleModel(model_name, provider=provider)


def model_gemini_2_5_flash_lite() -> Model:
  return google_model("gemini-2.5-flash-lite-preview-09-2025")


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


class TopicDetails(BaseModel):
  id: UUID
  name: str


class TopicLoader:
  
  def __init__(self, async_session: async_sessionmaker[AsyncSession]) -> None:
    self._db = async_session
    
  async def search_topics(self, search_keywords: list[str]) -> list[TopicDetails]:
    async with self._db() as session:
      topic_repo = TopicRepository(session)
          
      found_topics = await topic_repo.search_topics(search_keywords)
      return [
        TopicDetails(id=t.id, name=t.name) 
        for t in found_topics
      ]


@dataclass
class TopicAgentDeps:
  topic_loader: TopicLoader


class TopicProposal(BaseModel):
  id: Optional[UUID]
  name: str
  confidence: float
  
  class Config: # type: ignore
    extra = "forbid"
    

class TopicAgentResponse(BaseModel):
  topics: list[TopicProposal]
  
  class Config: # type: ignore
    extra = "forbid"


class TopicAgent:
  
  def __init__(self, model: Model, tpl_mgr: TemplateManager, topic_loader: TopicLoader):
    self._log = logging.getLogger("app.topicagent")
    self._tpl_mgr = tpl_mgr
    self._topic_loader = topic_loader
    
    self._init_agent(model)
  
  def _init_agent(self, model: Model):
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("topic_system", {}),
      deps_type=TopicAgentDeps,
      output_type=TopicAgentResponse
    )
    self._agent = agent
    
    @agent.tool
    async def search_topics(ctx: RunContext[TopicAgentDeps], search_keywords: list[str]) -> list[TopicDetails]:
      """
      Retrieves a list of topics based on the provided search keywords.

      Args:
        search_keywords (list[str]): A list of keywords used to search for matching topics.
          Each keyword is compared against the topic's name using full-text search.
          Each element can include multiple words for AND logic.
          Multiple elements are combined with OR logic across the list.

          For example:
            ["One Two", "Three"]
          searches for topics that match:
            ("One" AND "Two") OR ("Three")

      Returns:
        list[TopicDetails]: A list of topic details (ID and name) matching the search query.
          The returned topics are ordered by descending relevance - topics whose names
          more closely match the search terms appear first.
      """
      return await ctx.deps.topic_loader.search_topics(search_keywords)

  async def run(self, purposed_topics: list[str], temperature: float = 0.1) -> TopicAgentResponse:
    input = {
      "purposed_topics": purposed_topics
    }
    
    user_prompt = self._tpl_mgr.render("only_input", {"input": input})
    res = await self._agent.run(
      user_prompt,
      deps=TopicAgentDeps(topic_loader=self._topic_loader),
      model_settings=ModelSettings(temperature=temperature)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
  