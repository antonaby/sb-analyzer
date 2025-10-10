import asyncio
from typing import cast
from uuid import UUID
from celery import group
from celery.signals import worker_process_init, worker_shutting_down

from models.apidojo import DateRange, SortType
from models.apify import ActorRun
from models.common import AuthorDetails, PostDetails
from core.utils import is_url
from .main import worker_app

loop = None
apify_client = None
async_session = None
scraper_processor = None
video_processor = None


@worker_process_init.connect
def init_worker_process(**kwargs):
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  from core.agents.video import ClipTaggerClient
  from core.agents.transcribe import LemonfoxClient
  from core.agents.summary import SummaryAgent
  from core.processors.scraper import ScraperProcessor
  from core.processors.video import VideoProcessor
  from db.conf import create_db_engine, get_async_session
  
  load_dotenv()
  
  global loop
  loop = asyncio.new_event_loop()
  
  global apify_client
  apify_client = ApifyClient()
  
  global async_session
  engine = create_db_engine()
  async_session = get_async_session(engine)
  
  global scraper_processor
  scraper_processor = ScraperProcessor(async_session)
  
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent()
  
  global video_processor
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_session, "./videos")
  

@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  global loop
  if loop is not None:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@worker_app.task
def process_video(
  video_id: UUID,
  delete_downloaded_files: bool = True
) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global video_processor
  if video_processor is None:
    raise RuntimeError("Video processor not initialized")
  
  result = loop.run_until_complete(
    video_processor.run(video_id, delete_downloaded_files)
  )
  return cast(dict, result)


@worker_app.task
def save_video(author: AuthorDetails, post: PostDetails, process_new: bool = True) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global scraper_processor
  if scraper_processor is None:
    raise RuntimeError("Scraper processor not initialized")
  
  result = loop.run_until_complete(
    scraper_processor.run(author, post)
  )
  
  if process_new and result.get("new_video", False):
    process_video.delay(result["video_id"]) # type: ignore
  
  return cast(dict, result)


@worker_app.task
def run_apidojo_search(
  keywords: list[str], 
  date_range: DateRange,
  sort_type: SortType,
  location: str = "US", 
  max_items: int = 1000
) -> ActorRun:
  return _run_apidojo_scrapper(
    "search",
    keywords=keywords, 
    date_range=date_range, 
    sort_type=sort_type, 
    location=location, 
    max_items=max_items
  )


@worker_app.task
def run_apidojo_collect_urls(urls: list[str], max_items: int = 1000) -> ActorRun:
  return _run_apidojo_scrapper("collect_videos_by_urls", urls=urls, max_items=max_items)


def _run_apidojo_scrapper(func_name: str, **kwargs):
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global apify_client
  if apify_client is None:
    raise RuntimeError("Apify client not initialized")
  
  apidojo_client = apify_client.apidojo_tiktok_scrapper()
  
  func = getattr(apidojo_client, func_name)
  run, posts = loop.run_until_complete(
    func(**kwargs)
  )
  
  if len(posts) == 0:
    return run
  
  tasks = []
  
  for post in posts:
    author_url = post.get("channel", {}).get("url", "")
    video_url = post.get("postPage", "")
    download_url = post.get("video", {}).get("url", "")
    
    if is_url(author_url) and is_url(video_url) and is_url(download_url):
      author_details: AuthorDetails = {
        "url": author_url,
        "author_from": "tiktok"
      }
      post_details: PostDetails = {
        "url": video_url,
        "download_url": download_url,
        "post_from": "tiktok",
        "title": post.get("text", "no title"),
        "description": "",
        "hashtags": post.get("hashtags", []),
        "scraper": "apidojo",
        "source": cast(dict, post)
      }
      
      tasks.append(save_video.s(author_details, post_details)) # type: ignore
      
  job = group(tasks)
  job.apply_async()
  
  return run