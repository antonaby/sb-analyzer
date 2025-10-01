import asyncio
import os
from typing import Any
from apify_client import ApifyClientAsync



async def run_tiktok_scrapper() -> dict[str, Any]:
  # TODO: move somewhere else
  apify_client = ApifyClientAsync(os.getenv("APIFY_API_KEY"))
  
  actor_client = apify_client.actor('clockworks/tiktok-scraper')
  
  run_input = {
    "excludePinnedPosts": False,
    "hashtags": [
      "cat"
    ],
    "proxyCountryCode": "None",
    "resultsPerPage": 10,
    "scrapeRelatedVideos": False,
    "searchSection": "/video",
    "shouldDownloadAvatars": False,
    "shouldDownloadCovers": False,
    "shouldDownloadMusicCovers": False,
    "shouldDownloadSlideshowImages": False,
    "shouldDownloadSubtitles": False,
    "shouldDownloadVideos": True
  }
  
  call_result = await actor_client.call(run_input=run_input)
  
  if call_result is None:
    print('Actor run failed.')
    return {
      "ok": False
    }
   
  return {
    "ok": True,
    "result": call_result
  }
  
async def upload_tiktok_videos_to_s3(kv_store_id: str):
  # TODO: move somewhere else
  apify_client = ApifyClientAsync(os.getenv("APIFY_API_KEY"))
  
  kvStore = apify_client.key_value_store(kv_store_id)
  try:
    keys = await kvStore.list_keys()
  except Exception as e:
    print("An unexpected error occurred:", e)
    return
  
  video_keys = []
  
  for item in keys["items"]:
    if item["key"].lower().startswith("video"):
      video_keys.append(item["key"])
