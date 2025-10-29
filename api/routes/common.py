from pydantic import BaseModel


class OkResponse(BaseModel):
  result: bool
  msg: str


class CeleryJobDetails(BaseModel):
  celery_job_id: str
  celery_job_status: str
