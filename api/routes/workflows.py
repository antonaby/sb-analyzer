from fastapi import APIRouter

from api.routes.common import CeleryJobDetails
from models.apidojo import ApidojoActorSpec
from worker.tasks.workflows import run_apidojo_workflow


router = APIRouter(
  prefix="/workflows",
  tags=["workflows"],
)


@router.post("/apidojo")
def adhoc_categorize_challenges(spec: ApidojoActorSpec) -> CeleryJobDetails:
  job = run_apidojo_workflow.delay(spec.model_dump(mode="json"))

  return CeleryJobDetails(celery_job_id=job.id, celery_job_status=job.status)
