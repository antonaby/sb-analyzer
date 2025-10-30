from datetime import datetime
from typing import cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apify.actor import ActorRun
from apify.client import ApifyClient
from apify.tiktok.apidojo import TikTokPost
from core.processors.common import JobProcessor, AuthorDetails, PostDetails, ScrapedVideo, SavedPost
from db.models import VideoSource, Search
from db.repositories.authors import AuthorRepository
from db.repositories.searches import SearchRepository
from db.repositories.videos import VideoRepository
from models.apidojo import ApidojoActorSpec, ApidojoPostProcessorSpec
from utils.common import is_url


class ApidojoScraperRun(BaseModel):
  search_id: UUID
  run: ActorRun


class ApidojoActorProcessor(JobProcessor):

  def __init__(self, apify_client: ApifyClient, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._apify_client = apify_client

  async def run(self, spec: ApidojoActorSpec) -> ApidojoScraperRun:
    search, run = await self._run_scraper(spec)
    return ApidojoScraperRun(search_id=search.id, run=run)

  async def _run_scraper(self, spec: ApidojoActorSpec) -> tuple[Search, ActorRun]:
    search = await self._new_search("apidojo", spec.func, spec.args.model_dump(mode="json"))

    apidojo_client = self._apify_client.apidojo_tiktok_scrapper()
    func = getattr(apidojo_client, spec.func)

    actor_run: ActorRun
    posts: list[TikTokPost]

    try:
      actor_run = await func(**spec.args.model_dump())
      posts: list[TikTokPost] = await self._apify_client.get_dataset(actor_run["defaultDatasetId"])
    except Exception as e:
      await self._update_search(search.id, -1)
      raise e

    search = await self._update_search(search.id, len(posts))
    return search, actor_run

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


class ApidojoPostProcessResult(BaseModel):
  posts: list[SavedPost]


class ApidojoPostProcessor(JobProcessor):
  
  def __init__(self, apify_client: ApifyClient, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._apify_client = apify_client
    
  async def run(self, spec: ApidojoPostProcessorSpec) -> ApidojoPostProcessResult:
    dataset = await self._get_dataset(spec.search_id, spec.actor_run)
    result = await self._process_posts(dataset)
    return ApidojoPostProcessResult(posts=result)

  async def _get_dataset(self, search_id: UUID, actor_run: ActorRun) -> list[ScrapedVideo]:
    posts: list[TikTokPost] = await self._apify_client.get_dataset(actor_run["defaultDatasetId"])
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
          search_id=search_id,
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

    return videos

  async def _process_posts(self, dataset: list[ScrapedVideo]) -> list[SavedPost]:
    saved_posts: list[SavedPost] = []

    async with self._db() as session:
      video_repo = VideoRepository(session)
      author_repo = AuthorRepository(session)

      for video in dataset:
        saved_post = await self._save_post(video.post, video.author, video_repo, author_repo)
        saved_posts.append(saved_post)

      await session.commit()

    return saved_posts

  @staticmethod
  async def _save_post(post: PostDetails,
                       author: AuthorDetails,
                       video_repo: VideoRepository,
                       author_repo: AuthorRepository) -> SavedPost:

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

    await video_repo.add_scraped_data(video_model.id, post.model_dump(mode="json"))
    await video_repo.add_search(post.search_id, video_model.id, is_video_new)

    for hashtag in post.hashtags:
      hashtag_model = await video_repo.upsert_hashtag(hashtag, post.post_from)
      await video_repo.assign_hashtag(video_model.id, hashtag_model.id)

    return SavedPost(
      author_id=author_model.id,
      new_author=is_author_new,
      video_id=video_model.id,
      new_video=is_video_new,
    )
