from fastapi import APIRouter

from api.models import ApidojoScrapperRun, ApidojoCollectUrls
from worker.tasks import run_apidojo_search, run_apidojo_collect


router = APIRouter(
  prefix="/apidojo",
  tags=["apidojo"],
)


@router.post("/search")
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


@router.post("/collect")
def collect_videos(run: ApidojoCollectUrls):
  job = run_apidojo_collect.delay(
    urls=run.urls,
    max_items=run.max_items
  )

  return {
    "id": job.id,
    "status": job.status,
  }
