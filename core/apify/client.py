import os

from apify_client import ApifyClientAsync
from .tiktok.clockworks import ClockworksTiktokScrapper
from .tiktok.apidojo import ApidojoTiktokScrapper
from utils.common import var_or_exception

APIFY_API_KEY_VAR = "APIFY_API_KEY"

class ApifyClient:
  
  def __init__(self):
    key = var_or_exception(APIFY_API_KEY_VAR)
    self.client = ApifyClientAsync(key)
    
  def clockworks_tiktok_scrapper(self) -> ClockworksTiktokScrapper:
    return ClockworksTiktokScrapper(self.client)

  def apidojo_tiktok_scrapper(self) -> ApidojoTiktokScrapper:
    return ApidojoTiktokScrapper(self.client)
