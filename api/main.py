from celery.result import AsyncResult
from fastapi import FastAPI

from api.deps import *
from api.models import *
from api.routes import videos
from db.conf import test_db_conn
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository
from worker.main import worker_app
from worker.tasks import run_apidojo_search, run_apidojo_collect, process_video, identify_topics

app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")
app.include_router(videos.router)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_async_db)):
  result = await test_db_conn(db)
  db_status = result is not None and result == 1
  
  return {
    "db": db_status
  }


@app.post("/topics")
async def new_topic(request: CreateTopicRequest, topic_repo: TopicRepository = Depends(get_topic_repo)):
  topic = await topic_repo.create_topic(request.name)
  await topic_repo.commit()
  return topic 


@app.post("/apidojo/search")
def run_tiktok_scrapper(run: ApidojoScrapperRun):
  job = run_apidojo_search.delay(
    keywords=run.keywords, 
    date_range=run.date_range, 
    sort_type=run.sort_type, 
    location=run.location,
    max_items=run.max_items
  ) 
  
  return {
    "id": job.id,
    "status": job.status,
  }


@app.post("/apidojo/collect")
def collect_videos(run: ApidojoCollectUrls):
  job = run_apidojo_collect.delay(
    urls=run.urls,
    max_items=run.max_items
  )
  
  return {
    "id": job.id,
    "status": job.status,
  }


@app.post("/tasks/process-video/{video_id}")
def run_process_video_task(video_id: UUID):
  job = process_video.delay(video_id) # type: ignore

  return {
    "id": job.id,
    "status": job.status,
  }


@app.post("/tasks/identify_topics/{video_id}")
def run_identify_topics_task(video_id: UUID):
  job = identify_topics.delay(video_id)

  return {
    "id": job.id,
    "status": job.status,
  }


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app) 
  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }


@app.delete("/tasks/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app)
  job.revoke(terminate=True, signal='SIGTERM')

  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }


@app.get("/stat/unprocessed")
async def get_unprocessed_videos(video_repo: VideoRepository = Depends(get_video_repo)):
  videos = await video_repo.fetch_videos_under_processing()
  videos_short = [
    VideoProcessingStatus(
      id=v.id,
      url=v.url,
      jobs=[
        VideoProcessingDetails(
          job_id=j.job_id,
          source=j.source,
          created_at=j.created_at,
          started_at=j.started_at,
          finished_at=j.finished_at
        )
        for j in v.processing
      ]
    )
    for v in videos 
  ]
  
  return UnprocessedVideos(
    total=len(videos_short), 
    videos=videos_short
  )


@app.get("/topics")
async def get_all_topics(topic_repo: TopicRepository = Depends(get_topic_repo)):
  topics = await topic_repo.get_total_videos_per_topic()
  topics_short = [
    TopicsShort(id=t["id"], name=t["name"], total_videos=t["total_videos"])
    for t in topics
  ]
  
  return TotalTopics(total_topics=len(topics_short), topics=topics_short)
