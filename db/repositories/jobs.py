from typing import Sequence
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import insert, update, func, select, delete

from apify.tiktok.apidojo import DateRange, SortType, ApidojoFunc
from db.models import Job, ScraperJob
from db.repositories.common import BaseAsyncRepo, BadDataRepositoryError
from sqlalchemy.ext.asyncio import AsyncSession


APIDOJO_SCRAPER_NAME = "apidojo"

class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


class ApidojoCollectUrls(BaseModel):
  urls: list[str] = Field(min_length=1, description="At least one url")
  max_items: int


APIDOJO_SCRAPER_JOB_NAME = "apidojo.scraper"
class ApidojoScraperJob(BaseModel):
  func: ApidojoFunc
  args: ApidojoScrapperRun | ApidojoCollectUrls

APIDOJO_POST_PROCESSOR_JOB_NAME = "apidojo.postprocessor"
class ApidojoPostProcessorJob(BaseModel):
  search_id: UUID
  default_dataset_id: str

PROCESS_VIDEO_JOB_NAME = "video.process"
class ProcessVideoJob(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool

VIDEO_CATEGORIZATION_JOB_NAME = "video.categorization"
class VideoCategorizationJob(BaseModel):
  video_id: UUID

CHALLENGE_GEN_JOB_NAME = "challenge.gen"
class ChallengeGenJob(BaseModel):
  video_id: UUID
  pattern_group_id: UUID

CHALLENGE_CATEGORIZATION_JOB_NAME = "challenge.categorization"
class ChallengeCategorizationJob(BaseModel):
  challenge_id: UUID

CHALLENGE_TRANSLATION_JOB_NAME = "challenge.translation"
class TranslationJob(BaseModel):
  target_id: UUID
  langs: list[str]
  append: bool


class JobRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_job(self, name: str, meta: BaseModel | dict) -> Job:
    if isinstance(meta, BaseModel):
      meta = meta.model_dump(mode="json")

    stmt = insert(Job).values(name=name, meta=meta).returning(Job)

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def create_scraper_job(self, scraper_name: str, meta: BaseModel | dict, enabled: bool = False) -> ScraperJob:
    if isinstance(meta, BaseModel):
      meta = meta.model_dump(mode="json")

    stmt = insert(ScraperJob).values(scraper=scraper_name, meta=meta, enabled=enabled).returning(ScraperJob)

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def get_scraper_jobs(self, scraper_name: str) -> Sequence[ScraperJob]:
    stmt = select(ScraperJob).where(ScraperJob.scraper == scraper_name)

    result = await self._session.execute(stmt)
    return result.scalars().all()

  async def get_scraper_job(self, job_id: UUID) -> ScraperJob | None:
    stmt = select(ScraperJob).where(ScraperJob.id == job_id)

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def update_scraper_job(self,
                               job_id: UUID,
                               scraper_name: str | None,
                               meta: BaseModel | dict | None,
                               enabled: bool | None) -> ScraperJob | None:
    values = {}
    if scraper_name:
      values["scraper"] = scraper_name

    if meta:
      if isinstance(meta, BaseModel):
        meta = meta.model_dump(mode="json")

      values["meta"] = meta

    if enabled is not None:
      values["enabled"] = enabled

    if len(values) == 0:
      raise BadDataRepositoryError(f"Nonthing to update for scraper job {job_id}")

    stmt = (
      update(ScraperJob).
      where(ScraperJob.id == job_id).
      values(**values).
      returning(ScraperJob)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def delete_scraper_job(self, job_id: UUID) -> bool:
    stmt = delete(ScraperJob).where(ScraperJob.id == job_id)
    result = await self._session.execute(stmt)

    return result.rowcount == 1

  async def get_job(self, job_id: UUID) -> Job | None:
    return await self._session.get(Job, job_id)

  async def get_job_as(self, job_id: UUID, name: str) -> Job | None:
    stmt = select(Job).where(Job.id == job_id, Job.name == name)

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def set_job_started(self, job_id: UUID) -> Job | None:
    return await self._update_job(job_id, started_at=func.now())

  async def set_celery_job_id(self, job_id: UUID, celery_job_id: UUID) -> Job | None:
    return await self._update_job(job_id, celery_job_id=celery_job_id)

  async def set_job_finished(self, job_id: UUID, processing_error: bool) -> Job | None:
    return await self._update_job(job_id, finished_at=func.now(), processing_error=processing_error)

  async def _update_job(self, job_id: UUID, **kwargs) -> Job | None:
    stmt = (
      update(Job).
      where(Job.id == job_id).
      values(**kwargs).
      returning(Job)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def commit(self):
    await self._session.commit()
