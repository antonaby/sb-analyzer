from uuid import UUID

from celery import group

from db.repositories.jobs import APIDOJO_SCRAPER_NAME
from worker.main import worker_app
from worker.tasks.workflows import run_apidojo_workflow


@worker_app.task
def run_scrapers() -> dict:
  from db.repositories.jobs import APIDOJO_SCRAPER_NAME
  from worker.tasks.deps import loop, scraper_job_processor

  processor_result = loop.run_until_complete(scraper_job_processor.run_all())

  tasks = []
  for scraper, jobs in processor_result.jobs.items():
    if scraper == APIDOJO_SCRAPER_NAME:
      for job in jobs:
        tasks.append(run_apidojo_workflow.si(job))

  if len(tasks) > 0:
    scraper_job = group(tasks)
    scraper_job.apply_async()

  return processor_result.model_dump(mode="json")


@worker_app.task
def run_scraper(scraper_job_id: UUID) -> dict:
  from worker.tasks.deps import loop, scraper_job_processor

  processor_result = loop.run_until_complete(scraper_job_processor.run(scraper_job_id))
  if processor_result.name == APIDOJO_SCRAPER_NAME:
    run_apidojo_workflow.delay(processor_result.spec)
    return processor_result.model_dump(mode="json")

  raise ValueError("Unknow Scarper")
