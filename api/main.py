from typing import Optional
from uuid import UUID
from fastapi import Depends, FastAPI, Query
from celery.result import AsyncResult
from dotenv import load_dotenv
from api.models import ApidojoScrapperRun
from sqlalchemy.ext.asyncio import AsyncSession
from worker.tasks import run_apidojo_scrapper, process_video
from worker.main import worker_app
from db.conf import create_db_engine, get_async_session
from db.repositories.videos import VideoRepository

load_dotenv()

app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")

db_engine = create_db_engine()
AsyncSessionLocal = get_async_session(db_engine)

async def get_async_db():
  async with AsyncSessionLocal() as session:
    yield session


@app.get("/health")
async def health():
  return {"ok": True}


@app.post("/tiktok/apidojo/run")
def run_tiktok_scrapper(run: ApidojoScrapperRun):
  job = run_apidojo_scrapper.delay( # type: ignore
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
