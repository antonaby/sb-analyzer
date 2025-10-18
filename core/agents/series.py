import logging
from typing import List, TypedDict

from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings, Tool
from pydantic_ai.models import Model

from core.agents.common import TemplateManager, search_topics, TopicProposal, TopicAgentDepsLike, TopicAgent
from models.common import VideoData


class TopicsResponse(BaseModel):
  topics: List[TopicProposal]

class UserPromptInput(TypedDict):
  videos: list[VideoData]


class VideoSeriesAgent:

  def __init__(self, model: Model, tpl_mgr: TemplateManager, topic_agent: TopicAgent):
    self._log = logging.getLogger("app.series_analyzer")
    self._tpl_mgr = tpl_mgr
    self._topic_agent = topic_agent
    self._create_agent(model)

  def _create_agent(self, model: Model):
    agent = Agent(
      model,
      instructions=self._tpl_mgr.render("series_system", {}),
      output_type=TopicsResponse,
      deps_type=TopicAgentDepsLike,
      tools=[
        Tool(search_topics, takes_ctx=True)
      ]
    )
    self._agent = agent
    
  async def run(self, video_data: list[VideoData]) -> TopicsResponse:
    user_input: UserPromptInput = {
      "videos": video_data
    }
    
    user_prompt = self._tpl_mgr.render("only_input", {"input": user_input})
    run = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=0.1),
      deps=TopicAgentDepsLike(topic_agent=self._topic_agent)
    )
    
    usage = run.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return run.output
  