import logging
from typing import Any, Literal, cast, TypedDict
from apify_client import ApifyClientAsync
from core.apify.actor import BaseApifyActor
from models.apidojo import DateRange, SortType, TikTokPost
from models.apify import ActorRun


class ApidojoTikTokScrapperError(Exception):
  pass


class ApidojoTiktokScrapper(BaseApifyActor):
  
  def __init__(self, client: ApifyClientAsync):
    super().__init__(client)
    self.actor_client = client.actor('apidojo/tiktok-scraper')
    self._log = logging.getLogger("app.apify.tiktok.apidojo")
  
  async def search(self, 
    keywords: list[str], 
    date_range: DateRange,
    sort_type: SortType,
    location: str = "US", 
    max_items: int = 1000,
  ) -> tuple[ActorRun, list[TikTokPost]]:
    try:
      run_input = {
        "dateRange": date_range,
        "includeSearchKeywords": True,
        "keywords": keywords,
        "location": location,
        "maxItems": max_items,
        "sortType": sort_type
      }
      call_result = await self.actor_client.call(run_input=run_input, logger=self._log)
        
      if call_result is None:
        raise ApidojoTikTokScrapperError("no call result")
      
      actor_run = cast(ActorRun, call_result)
      dataset = await self._get_dataset(call_result["defaultDatasetId"])
            
      return actor_run, dataset
    except Exception as e:
      raise ApidojoTikTokScrapperError("run failed") from e
