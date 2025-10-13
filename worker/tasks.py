import asyncio
from datetime import datetime
from typing import cast
from uuid import UUID
from celery import group
from celery.signals import worker_process_init, worker_shutting_down

from models.apidojo import DateRange, SortType, TikTokPost
from models.apify import ActorRun
from models.common import AuthorDetails, PostDetails
from core.utils import is_url
from .main import worker_app

loop = None
apify_client = None
async_db = None
topic_processor = None
scraper_processor = None
video_processor = None


@worker_process_init.connect
def init_worker_process(**kwargs):
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  from core.agents.video import ClipTaggerClient
  from core.agents.transcribe import LemonfoxClient
  from core.agents.summary import SummaryAgent
  from core.processors.scraper import ScraperProcessor, TopicProcessor
  from core.processors.video import VideoProcessor
  from db.conf import create_db_engine, get_async_session
  
  load_dotenv()
  
  global loop
  loop = asyncio.new_event_loop()
  
  global apify_client
  apify_client = ApifyClient()
  
  global async_db
  engine = create_db_engine()
  async_db = get_async_session(engine)
  
  global topic_processor
  topic_processor = TopicProcessor(async_db)
  
  global scraper_processor
  scraper_processor = ScraperProcessor(async_db)
  
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent()
  
  global video_processor
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_db, "./videos")
  

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
  topic_id: UUID,
  keywords: list[str], 
  date_range: DateRange,
  sort_type: SortType,
  location: str = "US", 
  max_items: int = 1000
) -> ActorRun:
  return _run_apidojo_scrapper(
    topic_id,
    "search",
    keywords=keywords, 
    date_range=date_range, 
    sort_type=sort_type, 
    location=location, 
    max_items=max_items
  )


@worker_app.task
def run_apidojo_collect(topic_id: UUID, urls: list[str], max_items: int = 1000) -> ActorRun:
  return _run_apidojo_scrapper(topic_id, "collect_videos_by_urls", urls=urls, max_items=max_items)


def _run_apidojo_scrapper(topic_id: UUID, func_name: str, **kwargs):
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global apify_client
  if apify_client is None:
    raise RuntimeError("Apify client not initialized")
  
  global topic_processor
  if topic_processor is None:
    raise RuntimeError("TopicProcessor client not initialized")
  
  serach = loop.run_until_complete(topic_processor.new_search(topic_id, "apidojo", func_name, kwargs))
  
  apidojo_client = apify_client.apidojo_tiktok_scrapper()
  
  func = getattr(apidojo_client, func_name)
  
  posts: list[TikTokPost]
  run, posts = loop.run_until_complete(
    func(**kwargs)
  )
  
  if len(posts) == 0:
    loop.run_until_complete(
      topic_processor.update_search(serach["serach_id"], len(posts))
    )
    return run

  tasks = []
  
  for post in posts:
    channel = post.get("channel", {})
    author_url = channel.get("url", "")
    video_url = post.get("postPage", "")
    download_url = post.get("video", {}).get("url", "")
    
    if is_url(author_url) and is_url(video_url) and is_url(download_url):
      uploaded_at_str = post.get("uploadedAtFormatted", "1970-01-01T00:00:00+00:00")
      uploaded_at = datetime.fromisoformat(uploaded_at_str.replace("Z", "+00:00"))
      
      author_details: AuthorDetails = {
        "url": author_url,
        "author_from": "tiktok",
        "verified": channel.get("verified", None),
        "followers": channel.get("followers", None),
        "total_videos": channel.get("videos", None),
      }
      
      post_details: PostDetails = {
        "search_id": str(serach["serach_id"]),
        "url": video_url,
        "download_url": download_url,
        "post_from": "tiktok",
        "title": post.get("text", "no title"),
        "description": "",
        "hashtags": post.get("hashtags", []),
        "uploaded_at_iso": uploaded_at.isoformat(),
        "likes": post.get("likes", 0),
        "views": post.get("views", 0),
        "comments": post.get("comments", 0),
        "scraper": "apidojo",
        "source": cast(dict, post)
      }
      
      tasks.append(save_video.s(author_details, post_details)) # type: ignore
      
  job = group(tasks)
  job.apply_async()
  
  loop.run_until_complete(
    topic_processor.update_search(serach["serach_id"], len(posts))
  )
  return run
