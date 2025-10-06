import asyncio
import json
import logging
import os
import traceback
from typing import TypedDict, cast

import aiohttp
from jinja2 import Template
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ImageUrl
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile

from core.apify.tiktok import TikTokPost
from core.videos import VideoDetails, VideoFrame

LEMONFOX_API_KEY_ENV_VAR_NAME = "LEMONFOX_API_KEY"
INFERENCE_API_KEY_ENV_VAR_NAME = "INFERENCE_API_KEY"



SYSTEM_PROMPT_SUMMARY = """
  You are an assistant that analyzes structured video frame descriptions to infer the main idea of the entire video. 
  You will be given instructions on the output format, what to caption, and how to perform your job. 
  Follow those instructions.
"""

USER_PROMPT_SUMMARY_TEMPLATE = """
  You are given frame analyses for a single video. Aggregate them into an overall summary.
  You receive thw following data
  - Video metadata in the following format
    {
      "from": "video source like: tiktok, youtube shorts, etc",
      "title": "video title",
      "hashtags": [{
        "name": "one"
      },{
        "name": "two"
      },{
        "name": "three"
      }]
    }
  - A chronological list of frame analyses produced by another model, each following this schema:
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
  - You also receive a video transcription, as a list of stings:
    [
      "One", "Two", "Three"
    ]
    
  Rules:
  - Read all frame descriptions carefully. Be specific and literal.
  - Identify recurring themes, actions, settings, and objects.
  - Include interpretations of emotion, mood, or narrative if it's visually explicit.
  - Do atistic/cinematic analysis, but be factual, not speculative.
  - Condense into one clear, concise sentence that expresses the main idea or purpose of the video (e.g., "A cooking tutorial on making spaghetti," "A vlog of a trip to the beach," "A commercial for a sports drink").
  - 1-3 themes (1-2 words each), 1-3 video types
  - Plot: Describe the scene in short, direct sentences. Output only simple subject-verb-object descriptions. Example: 'dog runs across the street'.
  - Always output strictly valid JSON with proper escaping.
  - Output **only the JSON**, no extra text or explanation.
  
  Output format (return exactly this JSON):
  {
    "main_idea": "string (1 sentence)",
    "theme": ["theme_one", "theme_two"],
    "video_type": ['original', 'compilation', 'reaction', 'parody', 'review', 'tutorial', 'unboxing', 'explainer', 'vlog', 'livestream', 'podcast', 'interview', 'storytime', 'challenge', 'music video', 'dance', 'animation', 'short film', 'gaming', 'skits', 'documentary', 'news', 'debunking', 'analysis', 'shortform', 'memes', 'asmr', 'pov']
    "synopsis": "string (3-4 sentences)"
    "plot": "string, "
  }
  
  video metadata:
  {{ metadata_json }}
  
  frames:
  {{ desc_json }}
  
  transcription:
  {{ trans_json }}
"""


  
class Frame(BaseModel):
  frame_number: int
  timestamp: float
  details: FrameDetails
  


class VideoSummary(BaseModel):
  main_idea: str
  theme: list[str]
  video_type: list[str]
  synopsis: str
  plot: str
  
class Summary(BaseModel):
  frames: list[Frame]
  transcription: Transcript
  details: VideoSummary

class VideoAnalyzer:
  
  def __init__(self, concurrency: int = 10):
    self.log = logging.getLogger("app.analyzer")
    
    lemonfox_key = os.getenv(LEMONFOX_API_KEY_ENV_VAR_NAME)
    if not lemonfox_key or not lemonfox_key.strip():
      raise EnvironmentError(f"{LEMONFOX_API_KEY_ENV_VAR_NAME} not set or empty")
    
    self.lemonfox_key = lemonfox_key
    
    inference_key = os.getenv(INFERENCE_API_KEY_ENV_VAR_NAME)
    if not inference_key or not inference_key.strip():
      raise EnvironmentError(f"{INFERENCE_API_KEY_ENV_VAR_NAME} not set or empty")
      
    client = AsyncOpenAI(
      base_url="https://api.inference.net/v1",
      api_key=inference_key
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

    self.frame_semaphore = asyncio.Semaphore(concurrency)
  
  async def summary_tiktok(self, post: TikTokPost, video_datails: VideoDetails) -> Summary:
    frames, transcription = await asyncio.gather(
      self._analyze(video_datails["frames"]), 
      self._transcribe_audio(video_datails["audio"])
    )
    
    summary = await self._summary_tiktok(post, frames, transcription)
    
    return Summary(
      frames=frames,
      transcription=transcription,
      details=summary
    )
 
  async def _summary_tiktok(self, post: TikTokPost, frames: list[Frame], transcription: Transcript) -> VideoSummary:
    metadata_json = json.dumps({
      "from": "tiktok",
      "title": post.get("text", "no title"),
      "hashtags": post.get("hashtags", [])
    })
    
    only_desc = [r.details.model_dump() for r in frames]
    desc_json = json.dumps(only_desc)
    
    trans_segments = [s.text for s in transcription.segments]
    trans_json = json.dumps(trans_segments)
    
    self.log.debug("Start: Summary request")
    template = Template(USER_PROMPT_SUMMARY_TEMPLATE)
    user_prompt = template.render(metadata_json=metadata_json, desc_json=desc_json, trans_json=trans_json)
    
    res = await self._gm_agent.run(
      user_prompt,
      model_settings=OpenAIChatModelSettings(
        extra_body={
          "response_format": {
            "type": "json_object"
          }
        }
      )
    )
    usage = res.usage()
    self.log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return VideoSummary.model_validate_json(res.output)
  
  async def _analyze(self, frames: list[VideoFrame]) -> list[Frame]:
    tasks = [asyncio.create_task(self._analyze_frame(f)) for f in frames]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = [cast(Frame, r) for r in results if not isinstance(r, Exception)]
    errors = [
      "".join(traceback.format_exception_only(type(r), r)) 
      for r in results if isinstance(r, Exception)
    ]
    
    if len(errors) > 0:
      self.log.error(f"There are a few errors: {", ".join(errors)}")
    
    return successes
      
  async def _analyze_frame(self, frame: VideoFrame) -> Frame:
    async with self.frame_semaphore:
      self.log.debug("Start: Frame request")
      
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
      usage = res.usage()
      self.log.debug(f"Finish: frame request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
  
    return Frame(
      frame_number=frame["frame_number"],
      timestamp=frame["timestamp"],
      details=FrameDetails.model_validate_json(res.output)
    )
    
  async def _transcribe_audio(self, file_bytes: bytes) -> Transcript:
    url = "https://api.lemonfox.ai/v1/audio/transcriptions"
    headers = {
      "Authorization": f"Bearer {self.lemonfox_key}"
    }
    
    form = aiohttp.FormData()
    form.add_field("file", file_bytes,
      filename="audio.mp3",  
      content_type="audio/mpeg"
    )
    form.add_field("response_format", "verbose_json")
    form.add_field("speaker_labels", "true")
    form.add_field("translate", "true")

    async with aiohttp.ClientSession() as session:
      async with session.post(url, headers=headers, data=form) as response:
        result = await response.json()
        return Transcript.model_validate(result)
