import logging
import os
from typing import List, Literal, Optional, TypedDict

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from core.utils import var_or_exception
from db.repositories.videos import VideoDataLoader, VideoData
from db.repositories.topics import TopicLoader, TopicData


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


SYSTEM_PROMPT = """
You are a data labeling and ontology-mapping assistant. Your job:
- Identify recurring topics across a set of video descriptions from one author.
- Map those topics to an existing topics catalog (id, name).
- For each discovered topic, either return the existing topic id and name or propose a new, concise topic name if no catalog topic is sufficiently similar.

Rules:
- Treat the provided catalog as authoritative. Prefer mapping to an existing topic when meaning clearly overlaps.
- Consider semantic equivalence, synonyms, plural/singular, abbreviations, and common variants (e.g., “LLMs”, “large language models”, “foundation models”).
- Be conservative about creating new topics. Only propose a new one when no existing catalog topic covers the same concept.
- If multiple catalog topics could fit, pick the best single match (highest semantic overlap) and note alternates with lower confidence.
- Use short, specific names for proposed new topics (≤ 5 words when possible).
- Focus on recurring themes: do not create a “topic” that appears only once unless it's clearly central to the author's content.
- Keep reasoning internal; output must be valid JSON conforming to the schema below. Do not include extra text.

Similarity & thresholds:
- Strong match (map to existing): same core concept, even if phrased differently.
- Weak match (create new): only partial overlap or different core concept.
- If unsure, choose new and set confidence lower (e.g., 0.55-0.7).

Process (what you must do before output):
- Normalize descriptions (lowercase, strip boilerplate, ignore links/hashtags/usernames) and extract key phrases (n-grams, named entities, technical terms).
- Cluster recurring phrases into topics (semantic grouping). Discard trivial one-offs unless clearly central.
- Match each discovered topic against the catalog topic names using semantic similarity (consider synonyms, hyponyms, acronyms).
- Decide: If a clear existing match, set decision="existing" and include its topic_id. Otherwise set decision="new" and propose proposed_topic_name.

Assemble JSON strictly matching the schema.
"""

class SupportingVideo(BaseModel):
  video_id: int = Field(..., description="Id of the video in the input list")
  evidence: str = Field(..., description="Short phrase from description supporting the topic")

class AlternateConsidered(BaseModel):
  topic_id: str = Field(..., description="Topic ID from catalog that was considered but not chosen")
  similarity_hint: str = Field(..., description="Explanation of why this candidate was weaker")

class TopicDecision(BaseModel):
  canonical_topic: str = Field(..., description="Canonical label for the discovered topic cluster")
  decision: Literal["existing", "new"] = Field(..., description="Whether it maps to an existing topic or is new")
  topic_id: Optional[str] = Field(None, description="Existing catalog ID if decision=existing, else null")
  proposed_topic_name: Optional[str] = Field(None, description="Suggested concise name if decision=new, else null")
  supporting_videos: List[SupportingVideo] = Field(..., description="List of videos supporting this topic")
  alternates_considered: Optional[List[AlternateConsidered]] = Field(
      default_factory=list, description="Optional weaker catalog candidates considered"
  )
  confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the mapping decision (0-1)")

class TopicsResponse(BaseModel):
  topics: List[TopicDecision] = Field(..., description="List of discovered or matched topics")


class UserPromptContext(TypedDict):
  videos: list[VideoData]
  topics: list[TopicData]


class AuthorAnalyzer:

  def __init__(self, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.authoranalyzer")
    
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=SYSTEM_PROMPT,
      output_type=TopicsResponse
    )
    self._agent = agent
    
    self._load_template()
    
  def _load_template(self):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    self._user_prompt = env.get_template("author_tmp.jinja")
    
  async def analyze(self, video_loader: VideoDataLoader, topic_loader: TopicLoader) -> TopicsResponse:
    video_data = await video_loader.load_video_data()
    topics = await topic_loader.load_topics()
    
    context: UserPromptContext = {
      "videos": video_data,
      "topics": topics
    }
    
    user_prompt = self._user_prompt.render(context)
    run = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = run.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return run.output
  