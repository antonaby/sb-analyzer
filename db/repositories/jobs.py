from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, update, func, select

from db.models import Job
from db.repositories.common import BaseAsyncRepo
from sqlalchemy.ext.asyncio import AsyncSession


APIDOJO_SCRAPER_JOB_NAME = "apidojo.scraper"
class ApidojoScraperJob(BaseModel):
  func: str
  args: dict

APIDOJO_POST_PROCESSOR_JOB_NAME = "apidojo.postprocessor"
class ApidojoPostProcessorJob(BaseModel):
  search_id: UUID
  default_dataset_id: str

PROCESS_VIDEO_JOB_NAME = "video.process"
class ProcessVideoJob(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool

CATEGORIZATION_VIDEO_JOB_NAME = "video.categorization"
class CategorizationVideoJob(BaseModel):
  video_id: UUID

CHALLENGE_GEN_JOB_NAME = "challenge.gen"
class ChallengeGenJob(BaseModel):
  video_id: UUID
  pattern_group_id: UUID

CHALLENGE_TRANSLATION_JOB_NAME = "challenge.translation"
class TranslationJob(BaseModel):
  target_id: UUID
  langs: list[str]


class JobRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_job(self, name: str, meta: BaseModel | dict) -> Job:
    if isinstance(meta, BaseModel):
      meta = meta.model_dump(mode="json")

    stmt = insert(Job).values(name=name, meta=meta).returning(Job)

    result = await self._session.execute(stmt)
    return result.scalar_one()

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
