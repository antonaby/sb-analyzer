from celery.result import AsyncResult
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import *
from db.conf import create_db_engine, get_async_session, test_db_conn
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository
from worker.main import worker_app
from worker.tasks import run_apidojo_search, run_apidojo_collect, process_video, identify_topics

load_dotenv()

app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")

db_engine = create_db_engine()
AsyncSessionLocal = get_async_session(db_engine)

async def get_async_db():
  async with AsyncSessionLocal() as session:
    yield session


def get_video_repo(session: AsyncSession = Depends(get_async_db)) -> VideoRepository:
  return VideoRepository(session)


def get_topic_repo(session: AsyncSession = Depends(get_async_db)) -> TopicRepository:
  return TopicRepository(session)


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
  

@app.get("/videos/{video_id}")
async def get_video(
  video_id: UUID, 
  with_scraped_data: bool = Query(False, description="Add data produced by a scrapper"),
  with_annotations: bool = Query(False, deprecated="Add processed data for video"),
  with_meta: bool = Query(False, description="Add video meta"),
  video_repo: VideoRepository = Depends(get_video_repo)
):
  video = await video_repo.get_video_by_id(
    video_id, 
    with_scraped_data=with_scraped_data, 
    with_annotations=with_annotations, 
    with_meta=with_meta
  )
  return video


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


@app.get("/search")
async def search_videos(q: str = Query(default=None, min_length=1), db: AsyncSession = Depends(get_async_db)):
  repo = VideoRepository(db)
  
  videos = await repo.find_videos(q)
  
  return {
    "videos": videos
  }
