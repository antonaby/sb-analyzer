from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_job_repo
from api.routes.common import OkResponse, CeleryJobDetails
from db.models import ScraperJob
from db.repositories.common import BadDataRepositoryError
from db.repositories.jobs import JobRepository, APIDOJO_SCRAPER_NAME
from models.apidojo import ApidojoActorSpec, ApidojoWorkflow
from worker.tasks.scrapers import run_scraper, run_scrapers

router = APIRouter(
  prefix="/scrapers",
  tags=["scrapers"],
)


class ScraperJobId(BaseModel):
  job_id: UUID


class ScraperJobDetails(BaseModel):
  id: UUID
  enabled: bool
  scraper: str
  created_at: datetime
  updated_at: datetime
  meta: dict


class ScraperJobs(BaseModel):
  total: int
  jobs: list[ScraperJobDetails]


def to_scraper_job_details(job: ScraperJob) -> ScraperJobDetails:
  return ScraperJobDetails(
    id=job.id,
    enabled=job.enabled,
    scraper=job.scraper,
    created_at=job.created_at,
    updated_at=job.updated_at,
    meta=job.meta
  )


@router.post("/apidojo")
async def create_apidojo_workflow_scraper_job(
    workflow: ApidojoWorkflow,
    enabled: bool = Query(True, description="Enable newly created scraper job"),
    job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobId:
  scraper_job = await job_repo.create_scraper_job(
    APIDOJO_SCRAPER_NAME, workflow, enabled=enabled
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


@router.post("/jobs/run")
def run_all_scraper_jobs():
  job = run_scrapers.delay()
  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)


@router.get("/jobs/{job_id}")
async def get_scraper_job(job_id: UUID, job_repo: JobRepository = Depends(get_job_repo)) -> ScraperJobDetails:
  job = await job_repo.get_scraper_job(job_id)
  if not job:
    raise HTTPException(404, f"Job {job_id} not found")

  return to_scraper_job_details(job)


@router.post("/jobs/{job_id}/run")
async def run_scraper_job(job_id: UUID, job_repo: JobRepository = Depends(get_job_repo)) -> CeleryJobDetails:
  scraper_job = await job_repo.get_scraper_job(job_id)
  if not scraper_job:
    raise HTTPException(404, f"Job {job_id} not found")

  job = run_scraper.delay(scraper_job.id)
  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)


class ScraperJobUpdateRequest(BaseModel):
  scraper: str | None = Field(None, description="Scraper name")
  meta: ApidojoActorSpec | None = Field(None, description="Scraper job meta")
  enabled: bool | None = Field(None, description="Enable or disable job")


@router.put("/jobs/{job_id}")
async def update_scraper_job(
    job_id: UUID,
    request: ScraperJobUpdateRequest,
    job_repo: JobRepository = Depends(get_job_repo)
) -> ScraperJobDetails:
  try:
    job = await job_repo.update_scraper_job(job_id, request.scraper, request.meta, request.enabled)
  except BadDataRepositoryError:
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
