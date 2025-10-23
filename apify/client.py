from typing import Any

from apify_client import ApifyClientAsync

from utils.common import var_or_exception
from .tiktok.apidojo import ApidojoTiktokScrapper
from .tiktok.clockworks import ClockworksTiktokScrapper

APIFY_API_KEY_VAR = "APIFY_API_KEY"

class ApifyClient:
  
  def __init__(self):
    key = var_or_exception(APIFY_API_KEY_VAR)
    self.client = ApifyClientAsync(key)
    
  def clockworks_tiktok_scrapper(self) -> ClockworksTiktokScrapper:
    return ClockworksTiktokScrapper(self.client)

  def apidojo_tiktok_scrapper(self) -> ApidojoTiktokScrapper:
    return ApidojoTiktokScrapper(self.client)

  async def get_dataset(self, dataset_id: str) -> list[Any]:
    dataset_client = self.client.dataset(dataset_id)
    items = await dataset_client.list_items()

    return items.items
