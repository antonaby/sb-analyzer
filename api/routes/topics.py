from fastapi import APIRouter

from api.deps import *
from api.models import CreateTopicRequest, TotalTopics
from api.routes.common import to_topic_shorts

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
async def get_all_topics(topic_repo: TopicRepository = Depends(get_topic_repo)):
  topics = await topic_repo.get_total_videos_per_topic()
  result = to_topic_shorts(topics)

  return TotalTopics(total=len(result), topics=result)
