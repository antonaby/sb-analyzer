import os

from typing import Any
from apify_client import ApifyClientAsync

from .videos import VideoFrame, split_video

def create_apify_client() -> ApifyClientAsync:
  return ApifyClientAsync(os.getenv("APIFY_API_KEY"))

async def run_tiktok_scrapper(apify_client: ApifyClientAsync) -> dict[str, Any]:
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
  
async def get_tiktok_video_keys(apify_client: ApifyClientAsync, kv_store_id: str) -> list[str]:
  kv_store = apify_client.key_value_store(kv_store_id)
  keys = await kv_store.list_keys()
  
  video_keys = []
  for item in keys["items"]:
    if item["key"].lower().startswith("video-"):
      video_keys.append(item["key"])
      
  return video_keys

async def download_video(apify_client: ApifyClientAsync, kv_store_id: str, record: str) -> bytes:
  kv_store = apify_client.key_value_store(kv_store_id)
  entry = await kv_store.get_record(record)
  
  if entry is None:
    raise ValueError(f"cannot get record: {kv_store_id}/{record}")
  
  return entry["value"]
