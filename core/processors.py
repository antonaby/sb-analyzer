import logging

from core.agents.summary import SummaryAgent, VideoSummary
from core.agents.transcribe import AudioData, LemonfoxClient
from core.agents.video import ClipTaggerClient, VideoData
from core.file import AudioFile, UrlVideoSource, VideoFile

from .apify.tiktok.clockwork import TikTokPost


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
    url = post.get("videoMeta", {}).get("downloadAddr")
    if not url:
      raise TikTokVideoProcessorError("No video url")
    
    source = await UrlVideoSource.new(url, self._tmp_dir)
    video = VideoFile(source)  
    audio = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video)
    audio_data = AudioData(self._lm_client, audio)
    
    summary = await self._agent.summary_tiktok(post, video_data, audio_data)
    source.delete()
    
    return summary
