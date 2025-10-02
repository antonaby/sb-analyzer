import os

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile

from core.videos import VideoFrame

class ClipTaggerResponse(BaseModel):
  """Schema for structured video frame analysis"""
  description: str
  objects: list[str] = Field(..., max_length=10)
  actions: list[str] = Field(..., max_length=5)
  environment: str
  content_type: str
  specific_style: str
  production_quality: str
  summary: str
  logos: list[str]

SYSTEM_PROMPT_FRAMES = """You are an image annotation API trained to analyze video keyframes.
You will be given instructions on the output format, what to caption, and how to perform your job.
Follow those instructions. For descriptions and summaries, provide them directly and do not lead them with
'This image shows' or 'This keyframe displays...', just get right into the details."""

USER_PROMPT_FRAMES = """Analyze this video frame and return a JSON object with these exact fields:

{
  "description": "Detailed factual account of what's visible (2 sentences max)",
  "objects": ["list of visible objects with details"],
  "actions": ["list of visible actions"],
  "environment": "Description of the setting",
  "content_type": "Type like 'real-world footage', 'animation', 'CGI', etc",
  "specific_style": "Genre/aesthetic like 'vlog', 'documentary', 'tutorial', etc",
  "production_quality": "Like 'professional', 'amateur', 'TV broadcast', etc",
  "summary": "One sentence summary",
  "logos": ["any visible logos"]
}

Be specific and literal. Focus only on what is explicitly visible.
Maximum 10 objects and 5 actions. Return only valid JSON."""

client = AsyncOpenAI(
  base_url="https://api.inference.net/v1",
  api_key=os.getenv("INFERENCE_API_KEY")
)

model = OpenAIChatModel(
  model_name="inference-net/cliptagger-12b",
  provider=OpenAIProvider(openai_client=client),
  profile=OpenAIModelProfile(
    supports_tools=False
  )
)

frame_analyzer = Agent(
  model=model,
  system_prompt=SYSTEM_PROMPT_FRAMES,
)

async def analyze_frame(frame: VideoFrame) -> ClipTaggerResponse:
  res = await frame_analyzer.run(
    [
      USER_PROMPT_FRAMES,
      ImageUrl(url=f"data:image/jpeg;base64,{frame['base64']}")
    ],
    model_settings=OpenAIChatModelSettings(
      temperature=0.1,
      max_tokens=2000,
      extra_body={
        "response_format": {
          "type": "json_object"
        }
      }
    )
  )
  
  return ClipTaggerResponse.model_validate_json(res.output)
  