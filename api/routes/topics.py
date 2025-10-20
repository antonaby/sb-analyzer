from fastapi import APIRouter
from api.deps import *
from api.models import CreateTopicRequest, TopicsShort, TotalTopics

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
  topics_short = [
    TopicsShort(id=t["id"], name=t["name"], total_videos=t["total_videos"])
    for t in topics
  ]

  return TotalTopics(total=len(topics_short), topics=topics_short)
