import logging

from core.agents.summary import PostDetails, SummaryAgent, VideoSummary
from core.agents.transcribe import AudioData, LemonfoxClient
from core.agents.video import ClipTaggerClient, VideoData
from core.file import AudioFile, UrlVideoSource, VideoFile
from core.utils import is_url

from .apify.tiktok.apidojo import TikTokPost


class TikTokVideoProcessorError(Exception):
  pass


class TikTokVideoProcessor:
  
  def __init__(self, ct_client: ClipTaggerClient, lm_client: LemonfoxClient, agent: SummaryAgent, tmp_dir: str):
    self._log = logging.getLogger("app.processor.tiktok")
    self._ct_client = ct_client
    self._lm_client = lm_client
    self._agent = agent
    self._tmp_dir = tmp_dir
    
  async def process_video(self, post: TikTokPost) -> VideoSummary:
    url = post.get("video", {}).get("url", "")
    if not is_url(url):
      raise TikTokVideoProcessorError("No video url")
    
    source = await UrlVideoSource.new(url, self._tmp_dir)
    video = VideoFile(source)  
    audio = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video)
    audio_data = AudioData(self._lm_client, audio)
    
    post_details: PostDetails = {
      "post_from": "tiktok",
      "title": post.get("text", "no title"),
      "hashtags": post.get("hashtags", [])
    }
    
    summary = await self._agent.summary_tiktok(post_details, video_data, audio_data)
    source.delete()
    
    return summary
