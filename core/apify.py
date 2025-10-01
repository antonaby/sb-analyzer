import asyncio
import os
from apify_client import ApifyClientAsync
import logging

async def runTikTokScrapper():
  
  apify_client_logger = logging.getLogger('apify_client')
  apify_client_logger.setLevel(logging.DEBUG)
  apify_client_logger.addHandler(logging.StreamHandler())
  
  apify_logger = logging.getLogger("apify")
  apify_logger.setLevel(logging.DEBUG)

  handler = logging.StreamHandler()
  handler.setFormatter(logging.Formatter(
      "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  ))
  apify_logger.addHandler(handler)
  
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
    return
  
  dataset_client = apify_client.dataset(call_result['defaultDatasetId'])
  list_items_result = await dataset_client.list_items()
  
  kvStore = apify_client.key_value_store(call_result['defaultKeyValueStoreId'])
  

if __name__ == "__main__":
  asyncio.run(runTikTokScrapper())
