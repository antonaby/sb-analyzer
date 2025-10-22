from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apify.actor import ActorRun
from apify.client import ApifyClient
from apify.tiktok.apidojo import TikTokPost
from core.processors.common import JobProcessor, AuthorDetails, PostDetails
from db.models import VideoSource, Job, Search
from db.repositories.authors import AuthorRepository
from db.repositories.jobs import APIDOJO_SCRAPER_NAME, ApidojoScraperJob, POST_DETAILS_JOB_NAME, PostDetailsJob
from db.repositories.searches import SearchRepository
from db.repositories.videos import VideoRepository, prepare_scraped_data
from utils.common import is_url


class ScrapedVideo(BaseModel):
  post: PostDetails
  author: AuthorDetails


class ScraperRun(BaseModel):
  run: ActorRun
  videos: list[ScrapedVideo]


class ApidojoScrapperProcessor(JobProcessor):

  def __init__(self, apify_client: ApifyClient, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._apify_client = apify_client

  async def run(self, job_id: UUID) -> ScraperRun:
    job = await self.start_job(job_id, APIDOJO_SCRAPER_NAME)
    try:
      run, videos = await self._run_scraper(job)
      await self.set_job_finished(job_id, False)

      return ScraperRun(run=run, videos=videos)
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _run_scraper(self, job: Job) -> tuple[ActorRun, list[ScrapedVideo]]:
    job_meta = ApidojoScraperJob(**job.meta)
    search = await self._new_search("apidojo", job_meta.func, job_meta.args)

    apidojo_client = self._apify_client.apidojo_tiktok_scrapper()
    func = getattr(apidojo_client, job_meta.func)

    actor_run: ActorRun
    posts: list[TikTokPost]
    try:
      actor_run, posts = await func(**job_meta.args)
    except Exception as e:
      await self._update_search(search.id, -1)
      raise e

    if len(posts) == 0:
      await self._update_search(search.id, 0)
      return actor_run, []

    videos: list[ScrapedVideo] = []
    for post in posts:
      channel = post.get("channel", {})
      author_url = channel.get("url", "")
      video_url = post.get("postPage", "")
      download_url = post.get("video", {}).get("url", "")

      if is_url(author_url) and is_url(video_url) and is_url(download_url):
        uploaded_at_str = post.get("uploadedAtFormatted", "1970-01-01T00:00:00+00:00")
        uploaded_at = datetime.fromisoformat(uploaded_at_str.replace("Z", "+00:00"))
        hashtags = [s for s in post.get("hashtags", []) if isinstance(s, str) and s.strip()]

        author_details = AuthorDetails(
          url=author_url, author_from=VideoSource.tiktok,
          verified=channel.get("verified", None),
          followers=channel.get("followers", None),
          total_videos=channel.get("videos", None)
        )

        post_details = PostDetails(
          search_id=search.id,
          url=video_url,
          download_url=download_url,
          post_from=VideoSource.tiktok,
          title=post.get("title", "no title"),
          description="",
          hashtags=hashtags,
          uploaded_at=uploaded_at,
          likes=post.get("likes", 0),
          views=post.get("views", 0),
          comments=post.get("comments", 0),
          scraper="apidojo",
          source=cast(dict, post)
        )

        videos.append(ScrapedVideo(post=post_details, author=author_details))

    await self._update_search(search.id, len(posts))
    return actor_run, videos

  async def _new_search(self, scraper: str, kind: str, search_data: dict) -> Search:
    async with self._db() as session:
      search_repo = SearchRepository(session)
      search = await search_repo.create_search(scraper, kind, search_data)
      await session.commit()
      return search

  async def _update_search(self, search_id: UUID, total_videos: int) -> Search:
    async with self._db() as session:
      search_repo = SearchRepository(session)
      updated_search = await search_repo.update_search(search_id, total_videos)
      await session.commit()
      return updated_search


class SavePostResult(BaseModel):
  author_id: UUID
  new_author: bool
  video_id: UUID
  new_video: bool


class PostDetailsProcessor(JobProcessor):
  
  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    
  async def run(self, job_id: UUID) -> SavePostResult:
    job = await self.start_job(job_id, POST_DETAILS_JOB_NAME)
    try:
      result = await self._process_post(job)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _process_post(self, job: Job) -> SavePostResult:
    job_meta = PostDetailsJob(**job.meta)
    post = PostDetails(**job_meta.post)
    author = AuthorDetails(**job_meta.author)

    async with self._db() as session:
      author_repo = AuthorRepository(session)
      video_repo = VideoRepository(session)

      author_model, is_author_new = await author_repo.upsert_author(
        author.url,
        author.author_from,
        author.verified,
        author.followers,
        author.total_videos
      )
      
      video_model, is_video_new = await video_repo.upsert_video(
        post.url,
        post.post_from,
        author_model, 
        post.uploaded_at,
        post.likes,
        post.views,
        post.comments
      )
      scraped_data = prepare_scraped_data(video_model.id, post.model_dump(mode="json"))
      session.add(scraped_data)

      await video_repo.add_search(post.search_id, video_model.id, is_video_new)

      for hashtag in post.hashtags:
        hashtag_model = await video_repo.upsert_hashtag(hashtag, post.post_from)
        await video_repo.assign_hashtag(video_model.id, hashtag_model.id)
      
      await session.commit()

      return SavePostResult(
        author_id=author_model.id,
        new_author=is_author_new,
        video_id=video_model.id,
        new_video=is_video_new
      )
