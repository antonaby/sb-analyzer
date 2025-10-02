import json
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI
import pandas as pd

from core.videos import _frame_to_base64


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
  logos: List[str]
    
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

def caption_single_frame(client: OpenAI, frame_data, index: int):
  print(f"Processing frame {index}")
  
  base64_image = _frame_to_base64(frame_data['image'])

  messages = [
    {"role": "system", "content": SYSTEM_PROMPT_FRAMES},
    {"role": "user", "content": [
      {"type": "text", "text": USER_PROMPT_FRAMES},
      {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
    ]}
  ]

  response = client.chat.completions.create(
    model="inference-net/cliptagger-12b",
    messages=messages,
    temperature=0.1,
    max_tokens=2000,
    response_format={"type": "json_object"}  # THIS FORCES VALID JSON
  )
  
  print(f"Processed, prompt tokens: {response.usage.prompt_tokens}, completinion tokens {response.usage.completion_tokens}") # type: ignore[reportOptionalMemberAccess]

  data = response.choices[0].message.content or "{}"
  result_json = json.loads(data)
  return index, result_json, base64_image

SYSTEM_PROMPT_SUMMARY = """
You are an assistant that analyzes structured video frame descriptions to infer the main idea of the entire video. 
You receive a chronological list of frame/clip analyses produced by another model, each following this schema:
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

Your task:
1) Read all frame descriptions carefully.
2) Identify recurring themes, actions, settings, and objects.
3) Consider the content type, style, and production quality to refine interpretation.
4) Disregard irrelevant details (e.g., single-frame anomalies, background noise).
5) Condense into one clear, concise sentence that expresses the main idea or purpose of the video (e.g., "A cooking tutorial on making spaghetti," "A vlog of a trip to the beach," "A commercial for a sports drink").
6) Be factual, not speculative.

Output format (return exactly this JSON):
{
  "main_idea": "string (1 sentence)",
  "theme": "string (1-5 words)",
  "synopsis": "string (2-3 sentences)"
}
"""

USER_PROMPT_SUMMARY = """
You are given frame/clip analyses for a single video. Please aggregate them into an overall summary per the system instructions. Return only valid JSON.
frames: 
"""

def video_summary(client: OpenAI, model: str, frames: pd.DataFrame):
  df_no_base64 = frames.drop(columns=['base64'])
  json_output = df_no_base64.to_json(orient='records', indent=2)
  
  messages = [
    {"role": "system", "content": SYSTEM_PROMPT_SUMMARY},
    {"role": "user", "content": [
      {"type": "text", "text": f"{USER_PROMPT_SUMMARY}\n{json_output}"}
    ]}
  ]
    
  response = client.chat.completions.create(
    model=model,
    messages=messages,
    response_format={"type": "json_object"}  # THIS FORCES VALID JSON
  )
  
  print(f"Processed, prompt tokens: {response.usage.prompt_tokens}, completinion tokens {response.usage.completion_tokens}") # type: ignore[reportOptionalMemberAccess]
  data = response.choices[0].message.content or "{}"
  result_json = json.loads(data)
  return result_json
