import logging
import asyncio
from concurrent.futures import ProcessPoolExecutor
from .apify.tiktok import ClockworksTiktokScrapper, TikTokPost
from .videos import split_video

class TikTokVideoProcessor:
  
  def __init__(self, tk_client: ClockworksTiktokScrapper, batch_size: int = 10):
    self.tk_client = tk_client
    self.batch_size = batch_size
    self.log = logging.getLogger("app.processor.tiktok")
    self.executor_pool = ProcessPoolExecutor(max_workers=5)
  
  def close(self):
    self.executor_pool.shutdown()
  
  async def run(self, theme: str):
    _, dataset = await self.tk_client.scrape_hashtags([theme], max_results=self.batch_size)
    
    video_tasks = [asyncio.create_task(self._process_video(v)) for v in dataset]
    video_results = await asyncio.gather(*video_tasks, return_exceptions=True)
    
    return video_results
    
  async def _process_video(self, video: TikTokPost):
    video_as_bytes = await self._get_video(video)
    
    loop = asyncio.get_running_loop()
    video_details = await loop.run_in_executor(self.executor_pool, split_video, video_as_bytes)

    return video_details
    
  async def _get_video(self, video: TikTokPost) -> bytes:  
    # TODO: add semaphore
    return await self.tk_client.download_video(video)
    
  