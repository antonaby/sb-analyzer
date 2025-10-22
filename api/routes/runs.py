from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends

from api.deps import get_job_repo
from api.models import JobRunDetails
from db.repositories.jobs import JobRepository, CHALLENGE_GEN_JOB_NAME, ChallengeGenJob
from worker.tasks.challenges import generate_challenges_for_topic

router = APIRouter(
  prefix="/runs",
  tags=["runs"],
)


@router.post("/challenge-gen")
async def run_challenge_gen(request: ChallengeGenJob, job_repo: JobRepository = Depends(get_job_repo)) -> JobRunDetails:
  job = await job_repo.create_job(
    CHALLENGE_GEN_JOB_NAME,
    request.model_dump(mode="json")
  )
  await job_repo.commit()

  celery_job: AsyncResult = generate_challenges_for_topic.delay(job_id=job.id)
  await job_repo.set_celery_job_id(job.id, UUID(celery_job.id))
  await job_repo.commit()

  return JobRunDetails(
    id=job.id,
    created_at=job.created_at,
    celery_job_id=celery_job.id,
    celery_job_status=celery_job.status
  )
