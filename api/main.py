from pydantic import BaseModel, Field
from fastapi import FastAPI
from celery.result import AsyncResult
from dotenv import load_dotenv
from core.apify.tiktok.apidojo import DateRange, SortType
from workers.tasks import run_apidojo_scrapper
from workers.main import app as worker_app


load_dotenv()
app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")


class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


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


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
  job = AsyncResult(task_id, app=worker_app) 
  return {
    "id": job.id,
    "status": job.status,
    "result": job.result
  }
