from dataclasses import dataclass
import logging
import os
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings, RunContext
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
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


def gemini_2_5_flash_lite() -> Model:
  return google_model("gemini-2.5-flash-lite-preview-09-2025")


def gemini_2_5_flash() -> Model:
  return google_model("gemini-2.5-flash-preview-09-2025")


def gemini_2_5_settings(budget: int) -> ModelSettings:
  return GoogleModelSettings(google_thinking_config={
    "include_thoughts": True,
    "thinking_budget": budget
  })


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


class TopicManager:
  
  def __init__(self, async_session: async_sessionmaker[AsyncSession]) -> None:
    self._db = async_session
    
  async def search_topics(self, search_keywords: list[str]) -> list[TopicDetails]:
    async with self._db() as session:
      repo = TopicRepository(session)
      await repo.topic_lock()
      
      single_words = [word for phrase in search_keywords for word in phrase.split()]
      found_topics = await repo.search_topics(single_words)
      return [
        TopicDetails(id=t.id, name=t.name) 
        for t in found_topics
      ]
      
  async def create_topic(self, name: str) -> TopicDetails:
    async with self._db() as session:
      repo = TopicRepository(session)
      await repo.topic_lock()
      
      found_topics = await repo.search_topics([name])
      if len(found_topics) > 0:
        t = found_topics[0] 
        return TopicDetails(id=t.id, name=t.name) 
      
      new_topic = await repo.create_topic(name)
      await session.commit()
      
    return TopicDetails(id=new_topic.id, name=new_topic.name)
  

@dataclass
class TopicAgentDeps:
  topic_manager: TopicManager


class TopicProposal(BaseModel):
  id: Optional[UUID]
  name: str
  confidence: float
  is_new: bool
  
  class Config: # type: ignore
    extra = "forbid"
    

class TopicAgentResponse(BaseModel):
  topics: list[TopicProposal]
  
  class Config: # type: ignore
    extra = "forbid"


class TopicAgent:
  
  def __init__(self, model: Model, tpl_mgr: TemplateManager, topic_loader: TopicManager):
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
    async def search_topics(ctx: RunContext[TopicAgentDeps], search_topics: list[str]) -> list[TopicDetails]:
      """
      Retrieves a list of topics based on the provided search topics.

      Args:
        search_topics (list[str]): A list of topic names to search for matching topics.
          For example:
            ["One - Two", "Three"]

      Returns:
        list[TopicDetails]: A list of topic details (ID and name) matching the search query.
          The returned topics are ordered by descending relevance - topics whose names
          more closely match the search terms appear first.
      """

      return await ctx.deps.topic_manager.search_topics(search_topics)
    
    @agent.tool
    async def create_topic(ctx: RunContext[TopicAgentDeps], name: str) -> TopicDetails:
      """
      Creates a new topic with the given name.
      
      Args:
        name (str): The name of the topic to be created.

      Returns:
          TopicDetails: Details about the newly created topic.
      """
      return await ctx.deps.topic_manager.create_topic(name)

  async def run(self, text: str, temperature: float = 0.01) -> TopicAgentResponse:
    input = {
      "text": text
    }
    
    user_prompt = self._tpl_mgr.render("only_input", {"input": input})
    res = await self._agent.run(
      user_prompt,
      deps=TopicAgentDeps(topic_manager=self._topic_loader),
      model_settings=ModelSettings(temperature=temperature)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output

@dataclass
class TopicAgentDepsLike:
  topic_agent: TopicAgent


async def search_topics_tool(ctx: RunContext[TopicAgentDepsLike], text: str) -> list[TopicProposal]:
  """
  Retrieves a list of topics based on the provided text.

  Args:
    text (str): A text for topics to extract

  Returns:
    list[TopicDetails]: A list of topic details (ID and name) matching the text.
      The returned topics are ordered by descending relevance - topics whose names
      more closely match the search terms appear first.
  """
  response = await ctx.deps.topic_agent.run(text)
  return response.topics
