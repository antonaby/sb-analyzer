import asyncio
import json
import logging
import os
import traceback
from typing import cast

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile

from core.videos import VideoFrame

INFERENCE_API_KEY_ENV_VAR_NAME = "INFERENCE_API_KEY"

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

SYSTEM_PROMPT_SUMMARY = """
  You are an assistant that analyzes structured video frame descriptions to infer the main idea of the entire video. 
  You will be given instructions on the output format, what to caption, and how to perform your job. 
  Follow those instructions.
"""

USER_PROMPT_SUMMARY = """
  You are given frame analyses for a single video. Aggregate them into an overall summary.
  You receive a chronological list of frame analyses produced by another model, each following this schema:
  {
    "timestamp": "number",
    "frame_number": "number",
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

  Rules:
  - Read all frame descriptions carefully. Be specific and literal.
  - Identify recurring themes, actions, settings, and objects.
  - Include interpretations of emotion, mood, or narrative if it's visually explicit.
  - Do atistic/cinematic analysis, but be factual, not speculative.
  - Condense into one clear, concise sentence that expresses the main idea or purpose of the video (e.g., "A cooking tutorial on making spaghetti," "A vlog of a trip to the beach," "A commercial for a sports drink").
  - Always output strictly valid JSON with proper escaping.
  - Output **only the JSON**, no extra text or explanation.
  
  Output format (return exactly this JSON):
  {
    "main_idea": "string (1 sentence)",
    "theme": "string (1-10 words)",
    "synopsis": "string (2-3 sentences)"
  }
  
  frame analyses: 
"""

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
  
class VideoSummary(BaseModel):
  main_idea: str
  theme: str
  synopsis: str

FrameResultType = tuple[VideoFrame, ClipTaggerResponse]

class VideoAnalyzer:
  
  def __init__(self):
    self.log = logging.getLogger("analyzer")
    
    key = os.getenv(INFERENCE_API_KEY_ENV_VAR_NAME)
    if not key or not key.strip():
      raise EnvironmentError(f"{INFERENCE_API_KEY_ENV_VAR_NAME} not set or empty")
      
    client = AsyncOpenAI(
      base_url="https://api.inference.net/v1",
      api_key=key
    )

    ct_model = OpenAIChatModel(
      model_name="inference-net/cliptagger-12b",
      provider=OpenAIProvider(openai_client=client),
      profile=OpenAIModelProfile(
        supports_tools=False
      )
    )
    self._ct_agent = Agent(
      model=ct_model,
      system_prompt=SYSTEM_PROMPT_FRAMES,
    )
    
    gemma_model = OpenAIChatModel(
      model_name="google/gemma-3-27b-instruct/bf-16",
      provider=OpenAIProvider(openai_client=client),
      profile=OpenAIModelProfile(
        supports_tools=False
      )
    )
    self._gm_agent = Agent(
      model=gemma_model,
      system_prompt=SYSTEM_PROMPT_SUMMARY,
    )
  
  async def summary(self, frames: list[VideoFrame]) -> VideoSummary:
    descriptions = await self._analyze(frames)
    return await self._summary(descriptions)
  
  async def _summary(self, descriptions: list[FrameResultType]) -> VideoSummary:
    only_desc = [d.model_dump_json() for _, d in descriptions]
    json_str = json.dumps(only_desc)
    
    res = await self._gm_agent.run(
      f"{USER_PROMPT_SUMMARY}\n{json_str}",
      model_settings=OpenAIChatModelSettings(
        extra_body={
          "response_format": {
            "type": "json_object"
          }
        }
      )
    )
    
    return VideoSummary.model_validate_json(res.output)
  
  async def _analyze(self, frames: list[VideoFrame]) -> list[FrameResultType]:
    tasks = [asyncio.create_task(self._analyze_frame(f)) for f in frames]
    # TODO: add semaphore
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = [cast(FrameResultType, r) for r in results if not isinstance(r, Exception)]
    errors = [
      "".join(traceback.format_exception_only(type(r), r)) 
      for r in results if isinstance(r, Exception)
    ]
    
    if len(errors) > 0:
      self.log.error(f"There are a few errors: {", ".join(errors)}")
    
    return successes
      
  async def _analyze_frame(self, frame: VideoFrame) -> FrameResultType:
    res = await self._ct_agent.run(
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
  
    return frame, ClipTaggerResponse.model_validate_json(res.output)
 