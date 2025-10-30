from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Query
from pydantic import BaseModel, Field

from api.deps import *
from db.repositories.topics import TopicWithVideoCount

router = APIRouter(
  prefix="/topics",
  tags=["topics"],
)


class CreateTopicGroupRequest(BaseModel):
  name: str = Field(min_length=3, description="Topic Group name")


@router.post("/groups")
async def new_topic(request: CreateTopicGroupRequest, topic_repo: TopicRepository = Depends(get_topic_repo)):
  topic = await topic_repo.create_topic_group(name=request.name)
  await topic_repo.commit()
  return topic


class CreateTopicRequest(BaseModel):
  group_id: UUID
  name: str = Field(min_length=3, description="Topic name")


@router.post("/")
async def new_topic(request: CreateTopicRequest, topic_repo: TopicRepository = Depends(get_topic_repo)):
  topic = await topic_repo.create_topic(name=request.name, group_id=request.group_id)
  await topic_repo.commit()
  return topic


class TotalTopics(BaseModel):
  total: int
  topics: list[TopicWithVideoCount]


@router.get("/")
async def get_all_topics(
    min_videos: int = Query(0, description="Min videos in topic to filter (including)"),
    topic_repo: TopicRepository = Depends(get_topic_repo)
) -> TotalTopics:
  topics = await topic_repo.get_total_videos_per_topic(min_videos=min_videos)

  return TotalTopics(total=len(topics), topics=topics)
