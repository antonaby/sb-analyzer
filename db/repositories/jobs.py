from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, update, func

from db.models import Job
from db.repositories.common import BaseAsyncRepo
from sqlalchemy.ext.asyncio import AsyncSession


CHALLENGE_GEN_JOB_NAME = "challenge_gen"
class ChallengeGenJob(BaseModel):
  topic_id: UUID


class JobRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_challenge_gen_job(self, job: ChallengeGenJob) -> Job:
    return await self._create_job(CHALLENGE_GEN_JOB_NAME, job.model_dump(mode="json"))

  async def get_job(self, job_id: UUID) -> Job | None:
    return await self._session.get(Job, job_id)

  async def set_job_started(self, job_id: UUID) -> Job | None:
    return await self._update_job(job_id, started_at=func.now())

  async def set_celery_job_id(self, job_id: UUID, celery_job_id: UUID) -> Job | None:
    return await self._update_job(job_id, celery_job_id=celery_job_id)

  async def set_job_finished(self, job_id: UUID, processing_error: bool) -> Job | None:
    return await self._update_job(job_id, finished_at=func.now(), processing_error=processing_error)

  async def _create_job(self, name: str, meta: dict) -> Job:
    stmt = insert(Job).values(name=name, meta=meta).returning(Job)

    result = await self._session.execute(stmt)
    return result.scalar_one()

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
