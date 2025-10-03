import logging
from .apify.tiktok import ClockworksTiktokScrapper, TikTokPost
from .videos import split_video
from .agents.analyzer import VideoAnalyzer

class TikTokVideoProcessor:
  
  def __init__(self, tk_client: ClockworksTiktokScrapper, analyzer: VideoAnalyzer):
    self.tk_client = tk_client
    self.analyzer = analyzer
    self.log = logging.getLogger("app.processor.tiktok")
    
  async def process_video(self, tk_post: TikTokPost):
    video_as_bytes = await self.tk_client.download_video(tk_post)
    # TODO: adjust interval 
    video_details = split_video(video_as_bytes, interval_seconds=10)

    summary = await self.analyzer.summary_tiktok(tk_post, video_details)

    return summary
    
  