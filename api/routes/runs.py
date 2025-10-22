from uuid import UUID

from celery.result import AsyncResult

from worker.tasks.challenges import generate_challenges_for_topic

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(
  prefix="/runs",
  tags=["runs"],
)


class ChallengeGenRequest(BaseModel):
  topic_id: UUID = Field(description="Id of Topic to generate Challenges")


@router.post("/challenge-gen")
async def run_challenge_gen(request: ChallengeGenRequest):
  job: AsyncResult = generate_challenges_for_topic.delay(topic_id=request.topic_id)

  return {
    "id": job.id,
    "status": job.status,
  }
