from typing import Any

from pydantic import BaseModel, Field


class OkResponse(BaseModel):
  result: bool
  msg: str


class CeleryJobDetails(BaseModel):
  celery_job_id: str
  celery_job_status: str
  result: Any | None = Field(None)
