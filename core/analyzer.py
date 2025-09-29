import json
from typing import List
from pydantic import BaseModel, Field
from openai import OpenAI

from core.vloader import frame_to_base64


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
    
SYSTEM_PROMPT = """You are an image annotation API trained to analyze video keyframes.
You will be given instructions on the output format, what to caption, and how to perform your job.
Follow those instructions. For descriptions and summaries, provide them directly and do not lead them with
'This image shows' or 'This keyframe displays...', just get right into the details."""

USER_PROMPT = """Analyze this video frame and return a JSON object with these exact fields:

{
    "description": "Detailed factual account of what's visible (4 sentences max)",
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
  
  base64_image = frame_to_base64(frame_data['image'])

  messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": [
          {"type": "text", "text": USER_PROMPT},
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
