import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.common import TemplateManager
from db.repositories.helpers import TextVideoData
from db.repositories.topics import TopicRepository


class TopicDetails(BaseModel):
  id: UUID
  name: str


class TopicProposal(BaseModel):
  id: Optional[UUID]
  name: str
  confidence: float
  is_new: bool

  class Config:  # type: ignore
    extra = "forbid"


class TopicManager:

  def __init__(self, async_session: async_sessionmaker[AsyncSession]) -> None:
    self._db = async_session

  async def search_topics(self, search_keywords: list[str]) -> list[TopicDetails]:
    async with self._db() as session:
      repo = TopicRepository(session)
      await repo.topic_lock()

      single_words = [word for phrase in search_keywords for word in phrase.split()]
      found_topics = await repo.search_topics_by_name(single_words)
      return [
        TopicDetails(id=t.id, name=t.name)
        for t in found_topics
      ]

  async def create_topics(self, proposals: list[TopicProposal]) -> list[TopicProposal]:
    async with self._db() as session:
      repo = TopicRepository(session)
      await repo.topic_lock()

      result: list[TopicProposal] = []

      for proposal in proposals:
        is_new = False
        topic = await repo.get_topic(proposal.id) if proposal.id else None
        if not topic:
          found_topics = await repo.search_topics_by_name([proposal.name])
          if len(found_topics) > 0:
            topic = found_topics[0]
          else:
            topic = await repo.create_topic(proposal.name)
            is_new = True

        result.append(
          TopicProposal(
            id=topic.id,
            name=topic.name,
            confidence=proposal.confidence,
            is_new=is_new,
          )
        )

      await session.commit()
      return result


@dataclass
class TopicAgentDeps:
  topic_manager: TopicManager


class TopicAgentResponse(BaseModel):
  topics: list[TopicProposal]

  class Config:  # type: ignore
    extra = "forbid"


class TopicAgent:

  def __init__(self, model: Model, tpl_mgr: TemplateManager, topic_manager: TopicManager):
    self._log = logging.getLogger("app.topic_agent")
    self._tpl_mgr = tpl_mgr
    self._topic_manager = topic_manager

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
    async def search_topics(ctx: RunContext[TopicAgentDeps], topic_names: list[str]) -> list[TopicDetails]:
      """
      Retrieves a list of topics based on the provided search topics.

      Args:
        topic_names (list[str]): A list of topic names to search for matching topics.
          For example:
            ["One - Two", "Three"]

      Returns:
        list[TopicDetails]: A list of topic details (ID and name) matching the search query.
          The returned topics are ordered by descending relevance - topics whose names
          more closely match the search terms appear first.
      """

      return await ctx.deps.topic_manager.search_topics(topic_names)

  async def run(self, video: TextVideoData, temperature: float = 0) -> list[TopicProposal]:
    user_prompt = self._tpl_mgr.render("only_input", {"input": video.model_dump(mode="json")})
    res = await self._agent.run(
      user_prompt,
      deps=TopicAgentDeps(topic_manager=self._topic_manager),
      model_settings=ModelSettings(temperature=temperature)
    )

    usage = res.usage()
    self._log.debug(
      f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}"
    )

    response: TopicAgentResponse = res.output
    topics = await self._topic_manager.create_topics(response.topics)

    return topics
