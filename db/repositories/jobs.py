from typing import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, update, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ScraperJob
from db.repositories.common import BaseAsyncRepo, BadDataRepositoryError


APIDOJO_SCRAPER_NAME = "apidojo"


class JobRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

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

  async def commit(self):
    await self._session.commit()
