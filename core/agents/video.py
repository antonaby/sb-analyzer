import asyncio
import logging
from openai import AsyncOpenAI
from core.utils import var_or_exception
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile


INFERENCE_API_KEY_VAR = "INFERENCE_API_KEY"
INFERENCE_API_URL = "https://api.inference.net/v1"
CLIPTAGGER_MODEL = "inference-net/cliptagger-12b"

SYSTEM_PROMPT_FRAMES = """
  You are an image annotation API trained to analyze YouTube video keyframes. 
  You will be given instructions on the output format, what to caption, and how to perform your job. 
  Follow those instructions. For descriptions and summaries, provide them directly and do not lead them with 'This image shows' or 'This keyframe displays...', just get right into the details.
"""

USER_PROMPT_FRAMES = """
  You are an image annotation API trained to analyze YouTube video keyframes. You must respond with a valid JSON object matching the exact structure below.
  Your job is to extract detailed **factual elements directly visible** in the image. Do not speculate or interpret artistic intent, camera focus, or composition. Do not include phrases like "this appears to be", "this looks like", or anything about the image itself. Describe what **is physically present in the frame**, and nothing more.
  Return JSON in this structure:

  {
      "description": "A detailed, factual account of what is visibly happening (4 sentences max). Only mention concrete elements or actions that are clearly shown. Do not include anything about how the image is styled, shot, or composed. Do not lead the description with something like 'This image shows' or 'this keyframe is...', just get right into the details.",
      "objects": ["object1 with relevant visual details", "object2 with relevant visual details", ...],
      "actions": ["action1 with participants and context", "action2 with participants and context", ...],
      "environment": "Detailed factual description of the setting and atmosphere based on visible cues (e.g., interior of a classroom with fluorescent lighting, or outdoor forest path with snow-covered trees).",
      "content_type": "The type of content it is, e.g. 'real-world footage', 'video game', 'animation', 'cartoon', 'CGI', 'VTuber', etc.",
      "specific_style": "Specific genre, aesthetic, or platform style (e.e., anime, 3D animation, mobile gameplay, vlog, tutorial, news broadcast, etc.)",
      "production_quality": "Visible production level: e.g., 'professional studio', 'amateur handheld', 'webcam recording', 'TV broadcast', etc.",
      "summary": "One clear, comprehensive sentence summarizing the visual content of the frame. Like the description, get right to the point.",
      "logos": ["logo1 with visual description", "logo2 with visual description", ...]
  }

  Rules:
  - Be specific and literal. Focus on what is explicitly visible.
  - Do NOT include interpretations of emotion, mood, or narrative unless it's visually explicit.
  - No artistic or cinematic analysis.
  - Always include the language of any text in the image if present as an object, e.g. "English text", "Japanese text", "Russian text", etc.
  - Maximum 10 objects and 5 actions.
  - Return an empty array for 'logos' if none are present.
  - Always output strictly valid JSON with proper escaping.
  - Output **only the JSON**, no extra text or explanation.
"""


class FrameContent(BaseModel):
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


class ClipTaggerClient:
  
  def __init__(
    self, 
    concurrency: int = 20,
    inference_url: str = INFERENCE_API_URL, 
    model_name: str = CLIPTAGGER_MODEL
  ) -> None:
    self._log = logging.getLogger("app.cliptagger")
    
    inference_key = var_or_exception(INFERENCE_API_KEY_VAR)
    
    client = AsyncOpenAI(
      base_url=inference_url,
      api_key=inference_key
    )
    model = OpenAIChatModel(
      model_name=model_name,
      provider=OpenAIProvider(openai_client=client),
      profile=OpenAIModelProfile(
        supports_tools=False
      )
    )
    self._agent = Agent(
      model=model,
      system_prompt=SYSTEM_PROMPT_FRAMES,
    )
    self._frame_semaphore = asyncio.Semaphore(concurrency)
  
  async def analyze(self, frame_base64: str, temperature: float = 0.1, max_tokens: int = 2000) -> FrameContent:
    async with self._frame_semaphore:
      self._log.debug("Start: Frame request")
      
      res = await self._agent.run(
        [
          USER_PROMPT_FRAMES,
          ImageUrl(url=f"data:image/jpeg;base64,{frame_base64}")
        ],
        model_settings=OpenAIChatModelSettings(
          temperature=temperature,
          max_tokens=max_tokens,
          extra_body={
            "response_format": {
              "type": "json_object"
            }
          }
        )
      )
      usage = res.usage()
      self._log.debug(f"Finish: frame request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
  
    return FrameContent.model_validate_json(res.output)
  