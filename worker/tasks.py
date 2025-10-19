import asyncio
from datetime import datetime
from typing import cast
from uuid import UUID
from celery import group
from celery.signals import worker_process_init, worker_shutting_down

from models.apidojo import DateRange, SortType, TikTokPost
from models.apify import ActorRun
from models.common import AuthorDetails, PostDetails
from utils.common import is_url
from .main import worker_app

loop = None
apify_client = None
async_db = None
search_processor = None
post_details_processor = None
video_processor = None


# TODO: recreate agents every time as the my preserve state (it's better to pass agents to "run" func)
@worker_process_init.connect
def init_worker_process(**kwargs):
  import logfire
  from dotenv import load_dotenv
  from core.apify.client import ApifyClient
  from core.video import ClipTaggerClient
  from core.transcribe import LemonfoxClient
  from core.agents.common import TemplateManager, gpt_5_nano
  from core.agents.topic import TopicManager, TopicAgent
  from core.agents.summary import SummaryAgent
  from core.processors.scraper import PostDetailsProcessor, SearchProcessor
  from core.processors.video import VideoProcessor
  from db.conf import create_db_engine, get_async_session

  logfire.configure()
  logfire.instrument_pydantic_ai()

  load_dotenv()
  tpl_mgr = TemplateManager()
  gpt5_nano = gpt_5_nano()

  global loop
  loop = asyncio.new_event_loop()

  global apify_client
  apify_client = ApifyClient()

  global async_db
  engine = create_db_engine()
  async_db = get_async_session(engine)

  global search_processor
  search_processor = SearchProcessor(async_db)

  global post_details_processor
  post_details_processor = PostDetailsProcessor(async_db)

  global video_processor
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent(gpt5_nano, tpl_mgr)
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_db, "./videos")

  topic_manager = TopicManager(async_db)
  topic_agent = TopicAgent(
    gpt5_nano,
    tpl_mgr,
    topic_manager
  )


@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  global loop
  if loop is not None:
    l_loop: asyncio.AbstractEventLoop = loop
    l_loop.run_until_complete(l_loop.shutdown_asyncgens())
    l_loop.close()


@worker_app.task
def process_video(
    video_id: UUID,
    delete_downloaded_files: bool = True
) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global video_processor
  if video_processor is None:
    raise RuntimeError("Video processor not initialized")

  from core.processors.video import VideoProcessor
  l_video_process: VideoProcessor = video_processor

  result = l_loop.run_until_complete(
    l_video_process.create_summary(video_id, delete_downloaded_files)
  )
  return cast(dict, result)


@worker_app.task
def save_video(author: AuthorDetails, post: PostDetails, process_new: bool = True) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global post_details_processor
  if post_details_processor is None:
    raise RuntimeError("Scraper processor not initialized")

  from core.processors.scraper import PostDetailsProcessor
  l_post_details_processor: PostDetailsProcessor = post_details_processor

  result = l_loop.run_until_complete(
    l_post_details_processor.save(author, post)
  )

  if (
    result["processing_error"]
    or (process_new and result["new_video"])
  ):
    process_video.delay(result["video_id"])  # type: ignore

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
def run_apidojo_collect(urls: list[str], max_items: int = 1000) -> ActorRun:
  return _run_apidojo_scrapper("collect_videos_by_urls", urls=urls, max_items=max_items)


def _run_apidojo_scrapper( func_name: str, **kwargs):
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global apify_client
  if apify_client is None:
    raise RuntimeError("Apify client not initialized")
  from core.apify.client import ApifyClient
  l_apify_client: ApifyClient = apify_client

  global search_processor
  if search_processor is None:
    raise RuntimeError("TopicProcessor client not initialized")
  from core.processors.scraper import SearchProcessor
  l_search_process: SearchProcessor = search_processor

  search = l_loop.run_until_complete(l_search_process.new_search("apidojo", func_name, kwargs))
  apidojo_client = l_apify_client.apidojo_tiktok_scrapper()
  func = getattr(apidojo_client, func_name)

  posts: list[TikTokPost]
  try:
    run, posts = l_loop.run_until_complete(
      func(**kwargs)
    )
  except Exception as e:
    l_loop.run_until_complete(
      l_search_process.update_search(search["search_id"], -1)
    )
    raise e

  if len(posts) == 0:
    l_loop.run_until_complete(
      l_search_process.update_search(search["search_id"], 0)
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
        "search_id": str(search["search_id"]),
        "url": video_url,
        "download_url": download_url,
        "post_from": "tiktok",
        "title": post.get("title", "no title"),
        "description": "",
        "hashtags": post.get("hashtags", []),
        "uploaded_at_iso": uploaded_at.isoformat(),
        "likes": post.get("likes", 0),
        "views": post.get("views", 0),
        "comments": post.get("comments", 0),
        "scraper": "apidojo",
        "source": cast(dict, post)
      }

      tasks.append(save_video.s(author_details, post_details))  # type: ignore

  job = group(tasks)
  job.apply_async()

  l_loop.run_until_complete(
    l_search_process.update_search(search["search_id"], len(posts))
  )

  return run
