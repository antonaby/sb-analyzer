from uuid import UUID

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_challenge_repo
from db.repositories.challenges import ChallengeRepository, TranslatedChallenge

router = APIRouter(
  prefix="/challenges",
  tags=["challenges"],
)


class ChallengeResponse(BaseModel):
  total: int
  challenges: list[TranslatedChallenge]


@router.get("/")
async def get_challenges_by_topic(
    topic_id: list[UUID] = Query(None, description="A list of Topic IDs to fetch"),
    lang: str = Query("en", description="Lang of the challenges"),
    challenge_repo: ChallengeRepository = Depends(get_challenge_repo)
) -> ChallengeResponse:
  if not topic_id or len(topic_id) == 0:
    raise HTTPException(status_code=400, detail="Topic IDs not provided")

  challenges = await challenge_repo.get_challenges_by_topics(topic_ids=topic_id, lang=lang)
  return ChallengeResponse(
    total=len(challenges),
    challenges=challenges
  )
