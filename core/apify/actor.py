from typing import Any

from apify_client import ApifyClientAsync
from abc import ABC


class BaseApifyActor(ABC):
  
  def __init__(self, client: ApifyClientAsync):
    self.client = client
  
  async def _get_dataset(self, dataset_id: str) -> list[Any]:
    dataset_client = self.client.dataset(dataset_id)
    items = await dataset_client.list_items()
    
    return items.items
