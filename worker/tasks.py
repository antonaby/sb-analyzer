import asyncio
from celery import group
from celery.signals import worker_process_init, worker_shutting_down

from core.models.apidojo import DateRange, SortType
from core.models.apify import ActorRun
from core.models.common import PostDetails
from core.utils import is_url
from .main import worker_app

loop = None
apify_client = None
video_processor = None


@worker_process_init.connect
def init_worker_process(**kwargs):
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  from core.agents.video import ClipTaggerClient
  from core.agents.transcribe import LemonfoxClient
  from core.agents.summary import SummaryAgent
  from core.processors import VideoProcessor
  
  load_dotenv()
  
  global loop
  loop = asyncio.new_event_loop()
  
  global apify_client
  apify_client = ApifyClient()
  
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent()
  
  global video_processor
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, "./videos")
  

@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  global loop
  if loop is not None:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@worker_app.task
def process_post(post: PostDetails) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global video_processor
  if video_processor is None:
    raise RuntimeError("Video processor not initialized")
  
  summary = loop.run_until_complete(video_processor.run(post))
  return summary.model_dump()
  

@worker_app.task
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
  
  if len(posts) == 0:
    return run
  
  tasks = []
  
  for post in posts:
    url = post.get("video", {}).get("url", "")
    if is_url(url):
      post_details: PostDetails = {
        "url": url,
        "post_from": "tiktok",
        "title": post.get("text", "no title"),
        "hashtags": post.get("hashtags", [])
      }
      tasks.append(process_post.s(post_details)) # type: ignore
      
  job = group(tasks)
  job.apply_async()
  
  return run
