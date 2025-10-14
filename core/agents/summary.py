import asyncio
from dataclasses import dataclass
import logging
from typing import TypedDict, cast
from pydantic_ai import Agent, RunContext, ModelSettings
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from core.agents.tpl import TemplateManager
from core.video import Frame, VideoData
from core.transcribe import AudioData
from models.common import PostDetails, VideoSummary
from core.utils import var_or_exception


GOOGLE_API_KEY_VAR = "GOOGLE_API_KEY"
GOOGLE_DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-09-2025"


SYSTEM_PROMPT_SUMMARY = """
You are an assistant that analyzes structured video frame descriptions and audio transcription to infer the main idea of the entire video. 
You will be given instructions on the output format, what to caption, and how to perform your job. 
Follow those instructions.

You receive the following data:
- Video Metadata 
- A chronological list of frame analyses produced by another model, each following this schema:
  {
    "time_sec": "time in seconds, fractions of a second are allowed, like 1, 2, 3, 4.5, 7.9",
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
- A chronological list of transcriptions produced by another model, each following this schema:
  {
    "text": "audio transcrion",
    "start_sec": "time in seconds, fractions of a second are allowed, like 1, 2, 3, 4.5, 7.9",
    "end_sec": "time in seconds, fractions of a second are allowed, like 1, 2, 3, 4.5, 7.9"
  }
  
Rules:
- Read all frame analyses carefully. Be specific and literal.
- Identify recurring themes, actions, settings, and objects.
- Include interpretations of emotion, mood, or narrative if it's explicit.
- Request more frame analyses to fill gaps.
- Do atistic/cinematic analysis, but be factual, not speculative.
- Condense into one clear, concise sentence that expresses the main idea or purpose of the video (e.g., "A cooking tutorial on making spaghetti," "A vlog of a trip to the beach," "A commercial for a sports drink").
- 1-3 themes (1-2 words each), 1-5 video types
- Synopsis: Describe the scene in short, direct sentences. Output only simple subject-verb-object descriptions with adjectives and adverbs. Example: 'black dog carefully runs across the street'.
- Output **only the JSON**, no extra text or explanation.

Output format (return exactly this JSON):
{
  "main_idea": "string (1 sentence)",
  "theme": ["theme_one", "theme_two"],
  "video_type": ['original', 'compilation', 'reaction', 'parody', 'review', 'tutorial', 'unboxing', 'explainer', 'vlog', 'livestream', 'podcast', 'interview', 'storytime', 'challenge', 'music video', 'dance', 'animation', 'short film', 'gaming', 'skits', 'documentary', 'news', 'debunking', 'analysis', 'shortform', 'memes', 'asmr', 'pov']
  "synopsis": ["dog runs across the street", "cat walks into room"]
}
"""

@dataclass
class SummaryAgentDeps:
  video: VideoData
  audio: AudioData
  

class UserPromptContext(TypedDict):
  post_from: str
  title: str
  hashtags: list[str]
  duration: float
  frames: list[dict]
  transcriptions: list[dict]


class SummaryAgent:
  
  def __init__(self, tpl_mgr: TemplateManager, model_name = GOOGLE_DEFAULT_MODEL):
    self._log = logging.getLogger("app.videosummary")
    self._tpl_mgr = tpl_mgr
    
    self._create_agent(model_name)
  
  def _create_agent(self, model_name: str):
    key = var_or_exception(GOOGLE_API_KEY_VAR)
    
    provider = GoogleProvider(api_key=key)
    model = GoogleModel(model_name, provider=provider)
    agent = Agent(
      model,
      instructions=SYSTEM_PROMPT_SUMMARY,
      deps_type=SummaryAgentDeps,
      output_type=VideoSummary
    )
    
    @agent.tool
    async def get_frame(ctx: RunContext[SummaryAgentDeps], time_sec: float) -> Frame:
      """
      Retrieves a video frame analysis at a specific time.

      Args:
        time_sec (float): The time position in the video (in seconds).
          Fractions of a second are allowed (e.g., 7.9).
      """
      return await ctx.deps.video.get_frame(time_sec)
    
    self._agent = agent

  async def summary(self, post: PostDetails, video: VideoData, audio: AudioData) -> VideoSummary:
    basic_frames, transcription = await asyncio.gather(
      video.get_n_frames(),
      audio.get_transcription()
    )
    
    context: UserPromptContext = {
      "post_from": post.get("post_from", "tiktok"),
      "title": post.get("text", "no title"),
      "hashtags": post.get("hashtags", []),
      "duration": video.get_duration(),
      "frames": [f.model_dump() for f in basic_frames],
      "transcriptions": [t.model_dump() for t in transcription]
    }
    
    user_prompt = self._tpl_mgr.render("author", cast(dict, context))
    res = await self._agent.run(
      user_prompt,
      deps=SummaryAgentDeps(video=video, audio=audio),
      model_settings=ModelSettings(temperature=0.1)
    )
    
    usage = res.usage()
    self._log.debug(f"Finish: summary request, input_tokens={usage.input_tokens}, output_tokens={usage.output_tokens}")
    
    return res.output
