from fastapi import APIRouter

from api.routes.common import CeleryJobDetails
from models.apidojo import ApidojoWorkflow, ApidojoDownloadWorkflow
from models.videos import VideoProcessingWorkflow, VideoBatchProcessingSpec
from worker.tasks.workflows import run_apidojo_workflow, run_video_processing_workflow, run_apidojo_download_workflow, batch_process_videos

router = APIRouter(
  prefix="/workflows",
  tags=["workflows"],
)


@router.post("/apidojo")
def apidojo_workflow(workflow: ApidojoWorkflow) -> CeleryJobDetails:
  job = run_apidojo_workflow.delay(workflow.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)


@router.post("/apidojo-download")
def apidojo_workflow(workflow: ApidojoDownloadWorkflow) -> CeleryJobDetails:
  job = run_apidojo_download_workflow.delay(workflow.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)


@router.post("/video-processing")
def video_processing_workflow(workflow: VideoProcessingWorkflow) -> CeleryJobDetails:
  job = run_video_processing_workflow.delay(workflow.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)


@router.post("/batch-process-videos")
def run_batch_process_videos_task(spec: VideoBatchProcessingSpec) -> CeleryJobDetails:
  job = batch_process_videos.delay(spec.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=job.result)
