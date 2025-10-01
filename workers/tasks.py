import asyncio
from .main import app
from core.apify import run_tiktok_scrapper, upload_tiktok_videos_to_s3

@app.task
def fetch_videos_and_upload(kv_store_id: str) -> int:
  asyncio.run(upload_tiktok_videos_to_s3(kv_store_id))
  
  return 0

@app.task
def scrape_tiktok_videos() -> int:
  result = asyncio.run(run_tiktok_scrapper())
  return 0
