from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_job_repo
from api.routes.common import OkResponse
from db.models import ScraperJob
from db.repositories.jobs import ApidojoScrapperRun, JobRepository, ApidojoCollectUrls, APIDOJO_SCRAPER_NAME, \
  ApidojoScraperJob, JobRepositoryError

router = APIRouter(
  prefix="/scrapers",
  tags=["scrapers"],
)


class ScraperJobId(BaseModel):
  job_id: UUID


class ScraperJobDetails(BaseModel):
  id: UUID
  scraper: str
  created_at: datetime
  updated_at: datetime
  last_job_id: UUID | None
  meta: dict


class ScraperJobs(BaseModel):
  total: int
  jobs: list[ScraperJobDetails]


def to_scraper_job_details(job: ScraperJob) -> ScraperJobDetails:
  return ScraperJobDetails(
    id=job.id,
    scraper=job.scraper,
    created_at=job.created_at,
    updated_at=job.updated_at,
    last_job_id=job.last_job_id,
    meta=job.meta
  )


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


@router.get("/jobs")
async def get_scraper_jobs(
    scraper: str = Query(description="Scraper name"),
    job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobs:
  jobs = await job_repo.get_scraper_jobs(scraper)
  return ScraperJobs(
    total=len(jobs),
    jobs=[
      to_scraper_job_details(j)
      for j in jobs
    ]
  )


@router.get("/jobs/{job_id}")
async def get_scraper_job(job_id: UUID, job_repo: JobRepository = Depends(get_job_repo)) -> ScraperJobDetails:
  job = await job_repo.get_scraper_job(job_id)
  if not job:
    raise HTTPException(404, f"Job {job_id} not found")

  return to_scraper_job_details(job)


class ScraperJobUpdateRequest(BaseModel):
  scraper: str | None = Field(None, description="Scraper name")
  meta: ApidojoScraperJob | None = Field(None, description="Scraper job meta")


@router.put("/jobs/{job_id}")
async def update_scraper_job(
    job_id: UUID,
    request: ScraperJobUpdateRequest,
    job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobDetails:
  try:
    job = await job_repo.update_scraper_job(job_id, request.scraper, request.meta)
  except JobRepositoryError as e:
    raise HTTPException(400, f"At least some of fields must be provided")

  if not job:
    raise HTTPException(404, f"Job {job_id} not found")

  await job_repo.commit()

  return to_scraper_job_details(job)


@router.delete("/jobs/{job_id}")
async def delete_scraper_job(job_id: UUID, job_repo: JobRepository = Depends(get_job_repo)) -> OkResponse:
  result = await job_repo.delete_scraper_job(job_id)
  if not result:
    raise HTTPException(404, f"Job {job_id} not found")

  await job_repo.commit()
  return OkResponse(result=True, msg="Scraper job has been deleted")
