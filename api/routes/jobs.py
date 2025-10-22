from celery.result import AsyncResult
from fastapi import APIRouter

from worker.main import worker_app


router = APIRouter(
  prefix="/jobs",
  tags=["jobs"],
)


@router.get("/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app)
  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }


@router.delete("/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app)
  job.revoke(terminate=True, signal='SIGTERM')

  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }
