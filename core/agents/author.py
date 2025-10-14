import logging
from typing import List, Literal, Optional, TypedDict, cast
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from core.agents.tpl import TemplateManager
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
- Semantic relevance first. A topic from the catalog must describe the same central concept as the cluster. For example:
  a) "Dog training" ≠ "Cat behavior (different species → different topic)
  b) "Cat videos" ≈ "Cat behavior" (same domain, minor variance acceptable)
  c) "Dog care" ≠ "Animal welfare" (only match if the description explicitly generalizes animals, not a specific one)

Process (what you must do before output):
- Normalize descriptions (lowercase, strip boilerplate, ignore links/hashtags/usernames) and extract key phrases (n-grams, named entities, technical terms).
- Cluster recurring phrases into topics (semantic grouping). Discard trivial one-offs unless clearly central.
- Match each discovered topic against the catalog topic names using semantic similarity (consider synonyms, hyponyms, acronyms).
- Decide: If a clear existing match, set decision="existing" and include its topic_id. Otherwise set decision="new" and propose proposed_topic_name.

Assemble JSON strictly matching the schema:
{
  "topics": [
    {
      "canonical_topic": "string",              // your canonical label for the cluster
      "decision": "existing" | "new",           // whether the topic is in the canalog or new
      "topic_id": "UUID | null",                // existing catalog id if decision=existing, else null
      "proposed_topic_name": "string | null",   // if decision=new, suggest a concise name; else null
      "supporting_videos": [                    // which descriptions support this topic
        { "video_id": UUID, "evidence": "very short phrase from description" }
      ],
      "alternates_considered": [                // optional: weaker candidates from catalog
        { "topic_id": "string", "similarity_hint": "why it was weaker" }
      ],
      "confidence": 0.0                         // 0-1 confidence in the decision
    }
  ]
}
"""

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


class UserPromptContext(TypedDict):
  videos: list[VideoData]
  topics: list[TopicData]


class AuthorAnalyzer:

  def __init__(self, tpl_mgr: TemplateManager, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.authoranalyzer")
    self._tpl_mgr = tpl_mgr
    
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=SYSTEM_PROMPT,
      output_type=TopicsResponse
    )
    self._agent = agent
    
  async def analyze(self, video_loader: VideoDataLoader, topic_loader: TopicLoader) -> TopicsResponse:
    video_data = await video_loader.load_video_data(max_videos=20)
    topics = await topic_loader.load_topics()
    
    context: UserPromptContext = {
      "videos": video_data,
      "topics": topics
    }
    
    user_prompt = self._tpl_mgr.render("author", cast(dict, context))
    run = await self._agent.run(
      user_prompt,
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = run.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return run.output
  