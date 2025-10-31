from celery.result import AsyncResult
from fastapi import APIRouter

from api.routes.common import CeleryJobDetails
from models.videos import VideoDownloadSpec
from worker.main import worker_app
from worker.tasks.videos import download_video


router = APIRouter(
  prefix="/tasks",
  tags=["tasks"],
)


@router.get("/{task_id}")
def get_task(task_id: str) -> CeleryJobDetails:
  job = AsyncResult(task_id, app=worker_app)
  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)

@router.post("/download-video")
def run_download_video_task(spec: VideoDownloadSpec) -> CeleryJobDetails:
  job = download_video.delay(spec.model_dump(mode="json"))
  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)
