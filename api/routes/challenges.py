from uuid import UUID

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_challenge_repo
from api.routes.common import OkResponse
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


@router.get("/{challenge_id}")
async def get_challenge(challenge_id: UUID, challenge_repo: ChallengeRepository = Depends(get_challenge_repo)):
  challenge = await challenge_repo.get_challenge(challenge_id, with_translations=True, with_videos=True)

  return challenge


class CreateChallengePatternGroupRequest(BaseModel):
  name: str


@router.post("/patterns/group")
async def create_pattern_group(
    request: CreateChallengePatternGroupRequest,
    challenge_repo: ChallengeRepository = Depends(get_challenge_repo)
):
  group = await challenge_repo.create_challenge_pattern_group(request.name)
  await challenge_repo.commit()

  return group


class CreateChallengePattern(BaseModel):
  value: str = Field(min_length=3)
  example: str = Field(min_length=3)


class CreateChallengePatternsRequest(BaseModel):
  group_id: UUID
  patterns: list[CreateChallengePattern] = Field(min_length=1)


@router.post("/patterns")
async def create_patterns(
    request: CreateChallengePatternsRequest,
    challenge_repo: ChallengeRepository = Depends(get_challenge_repo)
) -> OkResponse:
  for p in request.patterns:
    await challenge_repo.create_challenge_pattern(request.group_id, p.value, p.example)

  await challenge_repo.commit()

  return OkResponse(result=True, msg=f"{len(request.patterns)} challenges created")
