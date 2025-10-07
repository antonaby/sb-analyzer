import asyncio

from celery import signals
from core.apify.actor import ActorRun
from core.apify.client import ApifyClient
from core.apify.tiktok.apidojo import DateRange, SortType
from .main import app
from dotenv import load_dotenv


apify_client: ApifyClient | None = None


@signals.worker_process_init.connect
def init_worker_process(**kwargs):
  global apify_client
  load_dotenv()            
  apify_client = ApifyClient()


@app.task
def run_apidojo_scrapper(
  keywords: list[str], 
  date_range: DateRange,
  sort_type: SortType,
  location: str = "US", 
  max_items: int = 1000
) -> ActorRun:
  global apify_client
  if apify_client is None:
    raise RuntimeError("Apify client not initialized")
  
  apidojo_client = apify_client.apidojo_tiktok_scrapper()  
  
  run, posts = asyncio.run(
    apidojo_client.search(
      keywords=keywords, 
      date_range=date_range, 
      sort_type=sort_type, 
      location=location, 
      max_items=max_items
    )
  )

  return run
