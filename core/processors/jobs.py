from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.common import JobProcessor, JobProcessorError
from db.repositories.jobs import JobRepository, APIDOJO_SCRAPER_NAME
from models.apidojo import ApidojoWorkflow


class ScraperJobAllProcessorResult(BaseModel):
  jobs: dict[str, list[dict]]

class ScraperJobProcessorResult(BaseModel):
  name: str
  spec: dict


class ScraperJobProcessor(JobProcessor):

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)

  async def run_all(self) -> ScraperJobAllProcessorResult:
    jobs: dict[str, list[dict]] = {}

    async with self._db() as session:
      job_repo = JobRepository(session)
      apidojo_specs = await self._process_apidojo_jobs(job_repo)
      jobs[APIDOJO_SCRAPER_NAME] = [s.model_dump(mode="json") for s in apidojo_specs]

      await job_repo.commit()

    return ScraperJobAllProcessorResult(jobs=jobs)

  async def run(self, job_id: UUID) -> ScraperJobProcessorResult:
    async with self._db() as session:
      job_repo = JobRepository(session)
      job = await job_repo.get_scraper_job(job_id)
      if not job:
        raise JobProcessorError(f"Scraper job {job_id} not found")

      if job.scraper == APIDOJO_SCRAPER_NAME:
        spec = ApidojoWorkflow(**job.meta)
        return ScraperJobProcessorResult(name=APIDOJO_SCRAPER_NAME, spec=spec.model_dump(mode="json"))

      raise JobProcessorError(f"Unknown scraper for job {job_id} not found")

  @staticmethod
  async def _process_apidojo_jobs(repo: JobRepository) -> list[ApidojoWorkflow]:
    scraper_jobs = await repo.get_scraper_jobs(APIDOJO_SCRAPER_NAME)
    specs: list[ApidojoWorkflow] = []

    for scraper_job in scraper_jobs:
      if scraper_job.enabled:
        specs.append(ApidojoWorkflow(**scraper_job.meta))

    return specs
