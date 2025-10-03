import os

from apify_client import ApifyClientAsync

from .tiktok import ClockworksTiktokScrapper


APIFY_API_KEY_VAR = "APIFY_API_KEY"

class ApifyClient:
  
  def __init__(self):
    key = os.getenv(APIFY_API_KEY_VAR)
    if not key or not key.strip():
      raise EnvironmentError(f"{APIFY_API_KEY_VAR} not set or empty")
    
    self.client = ApifyClientAsync(key)
    
  def cw_tiktok_scrapper(self) -> ClockworksTiktokScrapper:
    return ClockworksTiktokScrapper(self.client)
