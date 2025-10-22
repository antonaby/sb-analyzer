from abc import ABC
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from db.models import Job, VideoSource
from db.repositories.jobs import JobRepository


class AuthorDetails(BaseModel):
  url: str
  author_from: VideoSource
  verified: bool | None
  followers: int | None
  total_videos: int | None


class PostDetails(BaseModel):
  search_id: UUID
  url: str
  download_url: str
  post_from: VideoSource
  title: str
  description: str
  hashtags: list[str]
  uploaded_at: datetime
  likes: int
  views: int
  comments: int
  scraper: str
  source: dict


class JobProcessorError(Exception):
  pass


class JobProcessor(ABC):

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker

  async def start_job(self, job_id: UUID, name: str) -> Job:
    async with self._db() as session:
      job_repo = JobRepository(session)
      job = await job_repo.get_job_as(job_id, name)
      if not job:
        raise JobProcessorError(f"Job {job_id} not found")

      await job_repo.set_job_started(job.id)
      await session.commit()
      return job

  async def set_job_finished(self, job_id, is_error: bool):
    async with self._db() as session:
      job_repo = JobRepository(session)
      await job_repo.set_job_finished(job_id, is_error)
      await session.commit()
