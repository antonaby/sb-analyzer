import asyncio
from datetime import datetime
from typing import cast

from celery import group
from celery.signals import worker_process_init, worker_shutting_down

from models.apidojo import DateRange, SortType, TikTokPost
from models.apify import ActorRun
from models.common import AuthorDetails, PostDetails
from models.processing import VideoProcessingPipline
from utils.common import is_url
from .main import worker_app

loop = None
apify_client = None
async_db = None
search_processor = None
video_processor = None
topic_processor = None


# TODO: recreate agents every time as they may preserve state (it's better to pass agents to "run" func)
@worker_process_init.connect
def init_worker_process(**kwargs):
  import logfire
  from dotenv import load_dotenv
  from apify.client import ApifyClient
  from core.video import ClipTaggerClient
  from core.transcribe import LemonfoxClient
  from core.agents.common import TemplateManager, gpt_5_nano
  from core.agents.topic import TopicManager, TopicAgent
  from core.agents.summary import SummaryAgent
  from core.processors.scraper import SearchProcessor
  from core.processors.video import VideoProcessor, TopicProcessor
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

  global video_processor
  clip_tagger_client = ClipTaggerClient()
  lemonfox_client = LemonfoxClient()
  summary_agent = SummaryAgent(gpt5_nano, tpl_mgr)
  video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_db, "./videos")

  global topic_processor
  topic_manager = TopicManager(async_db)
  topic_agent = TopicAgent(
    gpt5_nano,
    tpl_mgr,
    topic_manager
  )
  topic_processor = TopicProcessor(topic_agent, async_db)


@worker_shutting_down.connect
def clear_resources(sig, how, exitcode, **kwargs):
  global loop
  if loop is not None:
    l_loop: asyncio.AbstractEventLoop = loop
    l_loop.run_until_complete(l_loop.shutdown_asyncgens())
    l_loop.close()


@worker_app.task
def identify_topics(pipline: VideoProcessingPipline) -> dict:
  if not pipline["categorization_job_id"]:
    return {"skip": True}

  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global topic_processor
  if topic_processor is None:
    raise RuntimeError("Topic Processor not initialized")

  from core.processors.video import TopicProcessor
  l_topic_processor: TopicProcessor = topic_processor

  result = l_loop.run_until_complete(
    l_topic_processor.identify_topics(pipline["categorization_job_id"])
  )
  return cast(dict, result)


@worker_app.task
def process_video(pipeline: VideoProcessingPipline) -> dict:
  if not pipeline["summarizing_job_id"]:
    return { "skip": True }

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
    l_video_process.create_summary(
      pipeline["summarizing_job_id"],
      pipeline["delete_downloaded_files"]
    )
  )

  if pipeline["categorization_job_id"] and result["video_id"]:
    job = identify_topics.delay(pipeline)

    from core.processors.pipeline import PipelineProcessor
    pipeline_processor = PipelineProcessor(async_db)
    l_loop.run_until_complete(
      pipeline_processor.set_celery_job_id(pipeline["categorization_job_id"], job.id)
    )

  return cast(dict, result)


@worker_app.task
def run_pipline(author: AuthorDetails, post: PostDetails, force_run_pipeline: bool = False) -> dict:
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global async_db
  if async_db is None:
    raise RuntimeError("AsyncDB not initialized")

  from core.processors.scraper import PostDetailsProcessor
  post_processor: PostDetailsProcessor = PostDetailsProcessor(async_db)

  result = l_loop.run_until_complete(
    post_processor.save(author, post)
  )

  if result["new_video"] or force_run_pipeline:
    from core.processors.pipeline import PipelineProcessor
    pipeline_processor = PipelineProcessor(async_db)

    pipeline = l_loop.run_until_complete(
      pipeline_processor.create_pipeline(result["video_id"])
    )

    job = process_video.delay(pipeline)  # type: ignore
    l_loop.run_until_complete(
      pipeline_processor.set_celery_job_id(pipeline["summarizing_job_id"], job.id)
    )

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


def _run_apidojo_scrapper(func_name: str, **kwargs):
  global loop
  if loop is None:
    raise RuntimeError("Asyncio loop not initialized")
  l_loop: asyncio.AbstractEventLoop = loop

  global apify_client
  if apify_client is None:
    raise RuntimeError("Apify client not initialized")
  from apify.client import ApifyClient
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

      tasks.append(run_pipline.s(author_details, post_details))  # type: ignore

  job = group(tasks)
  job.apply_async()

  l_loop.run_until_complete(
    l_search_process.update_search(search["search_id"], len(posts))
  )

  return run
