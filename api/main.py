from typing import Optional
from uuid import UUID
from fastapi import Depends, FastAPI, Query
from celery.result import AsyncResult
from dotenv import load_dotenv
from api.models import ApidojoScrapperRun, ApidojoCollectUrls, CreateTopicRequest
from sqlalchemy.ext.asyncio import AsyncSession
from db.repositories.topics import TopicRepository
from worker.tasks import run_apidojo_search, run_apidojo_collect_urls, process_video
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
def collect_author_videos(run: ApidojoCollectUrls):
  job = run_apidojo_collect_urls.delay( # type: ignore
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

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app) 
  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }


@app.get("/search")
async def search_videos(q: str = Query(default=None, min_length=1), db: AsyncSession = Depends(get_async_db)):
  repo = VideoRepository(db)
  
  videos = await repo.find_videos(q)
  
  return {
    "videos": videos
  }
