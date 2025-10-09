import asyncio
import logging
import traceback
import copy
from typing import cast
from openai import AsyncOpenAI
from core.utils import var_or_exception
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile

from core.file import VideoFile, VideoFrame


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


class ClipTaggerError(Exception):
  pass


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
    self._api_semaphore = asyncio.Semaphore(concurrency)
  
  async def analyze(self, frame_base64: str, temperature: float = 0.1, max_tokens: int = 2000) -> FrameContent:
    try:
      async with self._api_semaphore:
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
    except Exception as e:
      raise ClipTaggerError(f"Cannot get frame content") from e


class Frame(FrameContent):
  frame_number: int
  time_sec: float


class VideoData:
  
  def __init__(self, ct_client: ClipTaggerClient, video_file: VideoFile, temperature: float = 0.1, max_tokens: int = 2000):
    self._log = logging.getLogger("app.videoframeanalyzer")
    self._ct_client = ct_client
    self._video_file = video_file
    self._temperature = temperature
    self._max_tokens = max_tokens
    self._frame_cache: list[Frame] = []
    self._cache_lock = asyncio.Lock()
  
  def get_duration(self) -> float:
    return self._video_file.get_duration()
  
  def get_total_frames(self) -> int:
    return self._video_file.get_total_frames()
  
  async def get_processed_frames(self) -> list[Frame]:
    async with self._cache_lock:
      cache_copy = copy.deepcopy(self._frame_cache)
      return cache_copy
    
  async def get_frame(self, timetamp: float) -> Frame:
    frame = self._video_file.get_frame(timetamp)  
    return await self._frame_content(frame)
  
  async def get_frames(self, interval: float = 10, **kwargs) -> list[Frame]:
    frames = self._video_file.get_frames_with_interval(interval=interval, **kwargs)
    return await self._process_frames(frames)
  
  async def get_n_frames(self, frame_n: int = 5, **kwargs) -> list[Frame]:
    frames = self._video_file.get_n_frames(frame_n=frame_n, **kwargs)
    return await self._process_frames(frames)
  
  async def _process_frames(self, frames: list[VideoFrame]) -> list[Frame]:
    tasks = [
      asyncio.create_task(self._frame_content(f)) 
      for f in frames
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = [cast(Frame, r) for r in results if not isinstance(r, Exception)]
    errors = [
      "".join(traceback.format_exception_only(type(r), r)) 
      for r in results if isinstance(r, Exception)
    ]
    
    if len(errors) > 0:
      self._log.error(f"There are a few errors: {", ".join(errors)}")
    
    return successes

  async def _frame_content(self, frame: VideoFrame) -> Frame:
    content = await self._ct_client.analyze(frame["base64"], self._temperature, self._max_tokens)
    
    result = Frame(
      **content.model_dump(), 
      frame_number=frame["frame_number"], 
      time_sec=frame["timestamp"]
    )
    
    async with self._cache_lock:
      self._frame_cache.append(result)
    
    return result
  