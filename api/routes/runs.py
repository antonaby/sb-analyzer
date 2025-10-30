from datetime import datetime
from uuid import UUID

from celery import Task
from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_job_repo
from db.repositories.jobs import JobRepository, CHALLENGE_GEN_JOB_NAME, ChallengeGenJob, TranslationJob, \
  CHALLENGE_TRANSLATION_JOB_NAME, APIDOJO_SCRAPER_JOB_NAME, PROCESS_VIDEO_JOB_NAME, ProcessVideoJob, \
  VIDEO_CATEGORIZATION_JOB_NAME, VideoCategorizationJob, ChallengeCategorizationJob, CHALLENGE_CATEGORIZATION_JOB_NAME
from models.apidojo import ApidojoSearch, ApidojoCollectUrls, ApidojoActorSpec
from worker.tasks.apidojo import run_apidojo_actor
from worker.tasks.challenges import generate_challenges_for_video, produce_challenge_translations, categorize_challenge, \
  adhoc_categorize_all_challenges
from worker.tasks.videos import process_video, categorize_video
from worker.tasks.scrapers import run_scrapers

router = APIRouter(
  prefix="/runs",
  tags=["runs"],
)


class JobRunDetails(BaseModel):
  id: UUID
  created_at: datetime
  celery_job_id: str
  celery_job_status: str


class ProcessVideoRequest(BaseModel):
  video_id: UUID


@router.post("/video/process")
async def run_process_video(request: ProcessVideoRequest, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    process_video,  # type: ignore[attr-defined]
    PROCESS_VIDEO_JOB_NAME,
    ProcessVideoJob(video_id=request.video_id, delete_downloaded_files=True),
    job_repo
  )


@router.post("/video/categorize")
async def run_categorize_video(request: ProcessVideoRequest, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    categorize_video,  # type: ignore[attr-defined]
    VIDEO_CATEGORIZATION_JOB_NAME,
    VideoCategorizationJob(video_id=request.video_id),
    job_repo
  )


@router.post("/apidojo/search")
async def run_tiktok_scrapper(request: ApidojoSearch, job_repo: JobRepository = Depends(get_job_repo))  -> JobRunDetails:
  return await _run_job_by_id(
    run_apidojo_actor,  # type: ignore[attr-defined]
    APIDOJO_SCRAPER_JOB_NAME,
    ApidojoActorSpec(func="search", args=request.model_dump(mode="json")),
    job_repo
  )


@router.post("/apidojo/collect")
async def collect_videos(request: ApidojoCollectUrls, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    run_apidojo_actor,  # type: ignore[attr-defined]
    APIDOJO_SCRAPER_JOB_NAME,
    ApidojoActorSpec(func="collect_videos_by_urls", args=request.model_dump(mode="json")),
    job_repo
  )


@router.post("/challenge/gen")
async def run_challenge_gen(request: ChallengeGenJob, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    generate_challenges_for_video,  # type: ignore[attr-defined]
    CHALLENGE_GEN_JOB_NAME,
    request,
    job_repo
  )


@router.post("/challenge/translate")
async def run_challenge_translation(
    request: TranslationJob,
    job_repo: JobRepository = Depends(get_job_repo)
) -> JobRunDetails:
  return await _run_job_by_id(
    produce_challenge_translations, # type: ignore[attr-defined]
    CHALLENGE_TRANSLATION_JOB_NAME,
    request,
    job_repo
  )


@router.post("/challenge/categorize")
async def run_challenge_translation(
    request: ChallengeCategorizationJob,
    job_repo: JobRepository = Depends(get_job_repo)
) -> JobRunDetails:
  return await _run_job_by_id(
    categorize_challenge, # type: ignore[attr-defined]
    CHALLENGE_CATEGORIZATION_JOB_NAME,
    request,
    job_repo
  )


@router.post("/adhoc/categorize-challenges")
def adhoc_categorize_challenges():
  job = adhoc_categorize_all_challenges.delay()

  return {
    "celery_job_id": job.id,
    "celery_job_status": job.status
  }


@router.post("/scrapers")
def run_scrapers_jobs():
  job = run_scrapers.delay()

  return {
    "celery_job_id": job.id,
    "celery_job_status": job.status
  }


async def _run_job_by_id(delay_func: Task, job_name: str, meta: BaseModel, job_repo: JobRepository) -> JobRunDetails:
  job = await job_repo.create_job(job_name, meta)
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
