from fastapi import APIRouter

from api.routes.common import CeleryJobDetails
from models.apidojo import ApidojoWorkflow
from models.videos import VideoProcessingWorkflow
from worker.tasks.workflows import run_apidojo_workflow, run_video_processing_workflow

router = APIRouter(
  prefix="/workflows",
  tags=["workflows"],
)


@router.post("/apidojo")
def apidojo_workflow(workflow: ApidojoWorkflow) -> CeleryJobDetails:
  job = run_apidojo_workflow.delay(workflow.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=None)


@router.post("/video-processing")
def video_processing_workflow(workflow: VideoProcessingWorkflow) -> CeleryJobDetails:
  job = run_video_processing_workflow.delay(workflow.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status, result=None)
