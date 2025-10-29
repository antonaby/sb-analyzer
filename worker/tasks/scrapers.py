from uuid import UUID

from celery import group

from db.repositories.jobs import APIDOJO_SCRAPER_NAME
from worker.main import worker_app
from worker.tasks.apidojo import run_apidojo_scraper


@worker_app.task
def run_scrapers() -> dict:
  from db.repositories.jobs import APIDOJO_SCRAPER_NAME
  from worker.tasks.deps import loop, scraper_job_processor

  processor_result = loop.run_until_complete(scraper_job_processor.run())

  tasks = []
  for scraper, jobs in processor_result.jobs.items():
    if scraper == APIDOJO_SCRAPER_NAME:
      for job in jobs:
        tasks.append(run_apidojo_scraper.si(job))

  if len(tasks) > 0:
    scraper_job = group(tasks)
    scraper_job.apply_async()

  return processor_result.model_dump(mode="json")


@worker_app.task
def run_scraper(scraper_job_id: UUID) -> dict:
  from worker.tasks.deps import loop, async_db
  from core.processors.jobs import create_exec_job_for_scraper_job

  scraper, job_id = loop.run_until_complete(create_exec_job_for_scraper_job(scraper_job_id, async_db))
  if scraper == APIDOJO_SCRAPER_NAME:
    run_apidojo_scraper.delay(job_id)
    return {
      "result": True,
      "job_id": job_id
    }

  return {
    "result": False
  }
