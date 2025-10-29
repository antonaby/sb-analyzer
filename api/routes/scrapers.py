from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_job_repo
from db.repositories.jobs import ApidojoScrapperRun, JobRepository, ApidojoCollectUrls, APIDOJO_SCRAPER_NAME, \
  ApidojoScraperJob

router = APIRouter(
  prefix="/scrapers",
  tags=["scrapers"],
)


class ScraperJobId(BaseModel):
  job_id: UUID


@router.post("/apidojo/search")
async def create_apidojo_search_scraper_job(
    request: ApidojoScrapperRun, job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobId:
  scraper_job = await job_repo.create_scraper_job(
    APIDOJO_SCRAPER_NAME, ApidojoScraperJob(func="search", args=request)
  )
  await job_repo.commit()

  return ScraperJobId(job_id=scraper_job.id)


@router.post("/apidojo/collect")
async def create_apidojo_collect_scraper_job(
    request: ApidojoCollectUrls, job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobId:
  scraper_job = await job_repo.create_scraper_job(
    APIDOJO_SCRAPER_NAME, ApidojoScraperJob(func="collect_videos_by_urls", args=request)
  )
  await job_repo.commit()

  return ScraperJobId(job_id=scraper_job.id)
