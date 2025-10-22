from uuid import UUID

from apify.actor import ActorRun
from worker.main import worker_app


@worker_app.task
def run_apidojo_scraper(job_id: UUID) -> ActorRun:
  from worker.tasks.deps import loop, apidojo_processor

  scraper_run = loop.run_until_complete(apidojo_processor.run(job_id))
  return scraper_run.run
