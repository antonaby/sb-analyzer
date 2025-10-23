from datetime import datetime
from uuid import UUID

from celery import Task
from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_job_repo
from apify.tiktok.apidojo import DateRange, SortType
from db.repositories.jobs import JobRepository, CHALLENGE_GEN_JOB_NAME, ChallengeGenJob, ChallengeTranslationJob, \
  CHALLENGE_TRANSLATION_JOB_NAME, APIDOJO_SCRAPER_JOB_NAME, ApidojoScraperJob
from worker.tasks.challenges import generate_challenges_for_topic, produce_challenge_translations
from worker.tasks.apidojo import run_apidojo_scraper


router = APIRouter(
  prefix="/runs",
  tags=["runs"],
)


class JobRunDetails(BaseModel):
  id: UUID
  created_at: datetime
  celery_job_id: str
  celery_job_status: str


class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


class ApidojoCollectUrls(BaseModel):
  urls: list[str] = Field(min_length=1, description="At least one url")
  max_items: int


@router.post("/apidojo/search")
async def run_tiktok_scrapper(request: ApidojoScrapperRun, job_repo: JobRepository = Depends(get_job_repo))  -> JobRunDetails:
  return await _run_job_by_id(
    run_apidojo_scraper,  # type: ignore[attr-defined]
    APIDOJO_SCRAPER_JOB_NAME,
    ApidojoScraperJob(func="search", args=request.model_dump(mode="json")),
    job_repo
  )


@router.post("/apidojo/collect")
async def collect_videos(request: ApidojoCollectUrls, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    run_apidojo_scraper,  # type: ignore[attr-defined]
    APIDOJO_SCRAPER_JOB_NAME,
    ApidojoScraperJob(func="collect_videos_by_urls", args=request.model_dump(mode="json")),
    job_repo
  )


@router.post("/challenge/gen")
async def run_challenge_gen(request: ChallengeGenJob, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    generate_challenges_for_topic,  # type: ignore[attr-defined]
    CHALLENGE_GEN_JOB_NAME,
    request,
    job_repo
  )


@router.post("/challenge/translate")
async def run_challenge_translation(
    request: ChallengeTranslationJob,
    job_repo: JobRepository = Depends(get_job_repo)
) -> JobRunDetails:
  return await _run_job_by_id(
    produce_challenge_translations, # type: ignore[attr-defined]
    CHALLENGE_TRANSLATION_JOB_NAME,
    request,
    job_repo
  )


async def _run_job_by_id(delay_func: Task, job_name: str, meta: BaseModel, job_repo: JobRepository) -> JobRunDetails:
  job = await job_repo.create_job(job_name, meta.model_dump(mode="json"))
  await job_repo.commit()

  celery_job: AsyncResult = delay_func.delay(job_id=job.id)
  await job_repo.set_celery_job_id(job.id, UUID(celery_job.id))
  await job_repo.commit()

  return JobRunDetails(
    id=job.id,
    created_at=job.created_at,
    celery_job_id=celery_job.id,
    celery_job_status=celery_job.status
  )
