from fastapi import APIRouter
from fastapi.params import Query

from api.deps import *
from api.models import CreateTopicRequest, TotalTopics

router = APIRouter(
  prefix="/topics",
  tags=["topics"],
)


@router.post("/")
async def new_topic(request: CreateTopicRequest, topic_repo: TopicRepository = Depends(get_topic_repo)):
  topic = await topic_repo.create_topic(request.name)
  await topic_repo.commit()
  return topic


@router.get("/")
async def get_all_topics(
    min_videos: int = Query(0, description="Min videos in topic to filter (including)"),
    topic_repo: TopicRepository = Depends(get_topic_repo)
) -> TotalTopics:
  topics = await topic_repo.get_total_videos_per_topic(min_videos=min_videos)

  return TotalTopics(total=len(topics), topics=topics)
