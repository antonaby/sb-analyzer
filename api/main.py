from typing import Optional
from uuid import UUID
from fastapi import Depends, FastAPI, Query
from celery.result import AsyncResult
from dotenv import load_dotenv
from api.models import *
from sqlalchemy.ext.asyncio import AsyncSession
from db.repositories.topics import TopicRepository
from worker.tasks import run_apidojo_search, run_apidojo_collect, process_video, process_author_videos
from worker.main import worker_app
from db.conf import create_db_engine, get_async_session, test_db_conn
from db.repositories.videos import VideoRepository

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


@app.post("/apidojo/serach")
def run_tiktok_scrapper(run: ApidojoScrapperRun):
  job = run_apidojo_search.delay( # type: ignore
    topic_id=run.topic_id,                                 
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
  job = run_apidojo_collect.delay( # type: ignore
    topic_id=run.topic_id,
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


@app.post("/tasks/process-author-videos")
def run_process_author_videos(task: TaskProcessAuthorVideos):
  job = process_author_videos.delay(task.author_id, task.max_videos) # type: ignore
  
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


@app.get("/search")
async def search_videos(q: str = Query(default=None, min_length=1), db: AsyncSession = Depends(get_async_db)):
  repo = VideoRepository(db)
  
  videos = await repo.find_videos(q)
  
  return {
    "videos": videos
  }
