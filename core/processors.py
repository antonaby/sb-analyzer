import logging

from .apify.tiktok import ClockworksTiktokScrapper, TikTokPost
from .videos import split_video
from .agents.embedding import Embedder
from .agents.analyzer import VideoAnalyzer

class TikTokVideoProcessor:
  
  def __init__(self, tk_client: ClockworksTiktokScrapper, analyzer: VideoAnalyzer, embedder: Embedder):
    self.log = logging.getLogger("app.processor.tiktok")
    self.tk_client = tk_client
    self.analyzer = analyzer
    self.embedder = embedder
    
  async def process_video(self, tk_post: TikTokPost):
    video_as_bytes = await self.tk_client.download_video(tk_post)
    # TODO: adjust interval 
    video_details = split_video(video_as_bytes, interval_seconds=10)

    summary = await self.analyzer.summary_tiktok(tk_post, video_details)
    summary_embedding = await self.embedder.get_embeddings(summary.details.main_idea)

    return summary_embedding
    
  