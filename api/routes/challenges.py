from uuid import UUID

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_challenge_repo
from db.repositories.challenges import ChallengeRepository, ChallengeWithTopic

router = APIRouter(
  prefix="/challenges",
  tags=["challenges"],
)


class ChallengeResponse(BaseModel):
  total: int
  challenges: list[ChallengeWithTopic]


@router.get("/")
async def get_challenges_by_topic(
    topic_ids: list[UUID] = Query(None, alias="topic_id", description="A list of Topic IDs to fetch"),
    langs: list[str] = Query(None, alias="lang", description="A list of languages"),
    min_difficulty: float | None = Query(None, description="Min challenge difficulty"),
    max_difficulty: float | None = Query(None, description="Max challenge difficulty"),
    challenge_repo: ChallengeRepository = Depends(get_challenge_repo)
) -> ChallengeResponse:
  if not topic_ids or len(topic_ids) == 0:
    raise HTTPException(status_code=400, detail="Topic IDs not provided")

  challenges = await challenge_repo.get_challenges_by_topics(
    topic_ids=topic_ids, min_difficulty=min_difficulty, max_difficulty=max_difficulty, langs=langs
  )
  return ChallengeResponse(
    total=len(challenges),
    challenges=challenges
  )
