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
video_series_processor = None

# TODO: recreate agents every time as the my preserve state (it's better to pass agents to "run" func)
@worker_process_init.connect
def init_worker_process(**kwargs):
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  from core.video import ClipTaggerClient
  from core.transcribe import LemonfoxClient
  from core.agents.common import TopicManager, TemplateManager
  from core.agents.summary import SummaryAgent
  from core.agents.series import VideoSeriesAgent
  from core.processors.scraper import ScraperProcessor, TopicProcessor
  from core.processors.video import VideoProcessor, VideoSeriesProcessor
  from db.conf import create_db_engine, get_async_session
  
  load_dotenv()
  tpl_mgr = TemplateManager()
  
  global loop
  loop = asyncio.new_event_loop()
  
  global apify_client
  apify_client = ApifyClient()
  
  global async_db
  engine = create_db_engine()
  async_db = get_async_session(engine)
  topic_loader = TopicManager(async_db)
  
  global topic_processor
  topic_processor = TopicProcessor(async_db)
  
  global scraper_processor
  scraper_processor = ScraperProcessor(async_db)
  
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent(tpl_mgr, topic_loader)
  
  global video_processor
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_db, "./videos")
  
  global video_series_processor
  video_series_agent = VideoSeriesAgent(tpl_mgr)
  video_series_processor = VideoSeriesProcessor(video_series_agent, async_db)
  

@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  global loop
  if loop is not None:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


@worker_app.task
def process_author_videos(author_id: UUID, max_videos: int) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  
  global video_series_processor
  if video_series_processor is None:
    raise RuntimeError("video Series processor not initialized")
  
  from db.repositories.videos import AuthorVideoLoader
  
  video_loader = AuthorVideoLoader(author_id, max_videos) 
  
  # result = loop.run_until_complete(
  #   video_series_processor.run(video_loader, topic_loader)
  # )
  
  # return cast(dict, result)
  
  return {"ok": True}
  

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
  
  if (
    result.get("processing_error", False) 
    or (process_new and result.get("new_video", False))
  ):
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
  try:
    run, posts = loop.run_until_complete(
      func(**kwargs)
    )
  except Exception as e:
    loop.run_until_complete(
      topic_processor.update_search(serach["serach_id"], -1)
    )
    raise e
  
  if len(posts) == 0:
    loop.run_until_complete(
      topic_processor.update_search(serach["serach_id"], 0)
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
