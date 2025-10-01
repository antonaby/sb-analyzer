import asyncio
from .main import app
from core.apify import create_apify_client, run_tiktok_scrapper, upload_tiktok_videos_to_s3

# TODO: add retries to all tasks

@app.task
def scrape_tiktok_videos() -> dict:
  apify_client = create_apify_client()
  return asyncio.run(run_tiktok_scrapper(apify_client))

@app.task
def fetch_videos_and_upload(kv_store_id: str) -> int:
  apify_client = create_apify_client()
  asyncio.run(upload_tiktok_videos_to_s3(apify_client, kv_store_id))
  return 0