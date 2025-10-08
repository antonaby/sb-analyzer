import asyncio
from celery import signals

from core.models.apidojo import DateRange, SortType
from core.models.apify import ActorRun
from .main import app


apify_client = None


@signals.worker_process_init.connect
def init_worker_process(**kwargs):
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  
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
