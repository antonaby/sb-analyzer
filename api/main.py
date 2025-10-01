import os

from fastapi import FastAPI
from celery.result import AsyncResult

from workers.tasks import scrape_tiktok_videos
from workers.main import app as worker_app

app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")

@app.get("/health")
async def health():
  return {"ok": True}

@app.post("/scrapper/tiktok/run")
async def run_tiktok_scrapper():
  result = scrape_tiktok_videos.delay() # type: ignore
  return {
    "id": result.id,
    "status": result.status
  }

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
  result = AsyncResult(task_id, app=worker_app) 
  return {
    "id": result.id,
    "status": result.status
  }
