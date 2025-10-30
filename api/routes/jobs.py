from celery.result import AsyncResult
from fastapi import APIRouter

from api.routes.common import CeleryJobDetails
from worker.main import worker_app


router = APIRouter(
  prefix="/jobs",
  tags=["jobs"],
)


@router.get("/{task_id}")
def get_task(task_id: str) -> CeleryJobDetails:
  job = AsyncResult(task_id, app=worker_app)
  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)
