from uuid import UUID

from celery import group

from apify.actor import ActorRun
from worker.main import worker_app
from worker.tasks.videos import process_video


@worker_app.task
def post_process_apidojo_dataset(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, apidojo_post_processor, async_db
  from worker.tasks.helpers import create_video_processing_jobs

  saved_posts = loop.run_until_complete(apidojo_post_processor.run(job_id))
  job_ids = loop.run_until_complete(create_video_processing_jobs(saved_posts.posts, async_db))

  if len(job_ids) > 0:
    tasks = [process_video.s(job_id) for job_id in job_ids]
    processing_job = group(tasks)
    processing_job.apply_async()

  return saved_posts.model_dump(mode="json")


@worker_app.task
def run_apidojo_scraper(job_id: UUID) -> ActorRun:
  from worker.tasks.deps import loop, apidojo_processor, async_db
  from worker.tasks.helpers import create_apidojo_post_process_job

  scraper_run = loop.run_until_complete(apidojo_processor.run(job_id))
  post_process_job_id = loop.run_until_complete(create_apidojo_post_process_job(scraper_run, async_db))
  post_process_apidojo_dataset.delay(post_process_job_id)

  return scraper_run.run
