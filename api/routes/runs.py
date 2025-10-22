from uuid import UUID

from celery import Task
from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_job_repo
from api.models import JobRunDetails
from db.repositories.jobs import JobRepository, CHALLENGE_GEN_JOB_NAME, ChallengeGenJob, ChallengeTranslationJob, \
  CHALLENGE_TRANSLATION_JOB_NAME
from worker.tasks.challenges import generate_challenges_for_topic, produce_challenge_translations

router = APIRouter(
  prefix="/runs",
  tags=["runs"],
)


@router.post("/challenge-gen")
async def run_challenge_gen(request: ChallengeGenJob, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  return await _run_job_by_id(
    generate_challenges_for_topic,  # type: ignore[attr-defined]
    CHALLENGE_GEN_JOB_NAME,
    request,
    job_repo
  )


@router.post("/challenge-translation")
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
