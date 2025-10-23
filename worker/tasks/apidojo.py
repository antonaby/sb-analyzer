from uuid import UUID

from apify.actor import ActorRun
from worker.main import worker_app


@worker_app.task
def post_process_apidojo_dataset(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, apidojo_post_processor

  saved_post = loop.run_until_complete(apidojo_post_processor.run(job_id))
  return saved_post.model_dump(mode="json")


@worker_app.task
def run_apidojo_scraper(job_id: UUID) -> ActorRun:
  from db.repositories.jobs import JobRepository, APIDOJO_POST_PROCESSOR_JOB_NAME, ApidojoPostProcessorJob
  from worker.tasks.deps import loop, apidojo_processor, async_db

  scraper_run = loop.run_until_complete(apidojo_processor.run(job_id))

  async def create_post_process_job() -> UUID:
    async with async_db() as session:
      job_repo = JobRepository(session)
      meta = ApidojoPostProcessorJob(
        search_id=scraper_run.search_id, default_dataset_id=scraper_run.run["defaultDatasetId"]
      )
      post_process_job = await job_repo.create_job(APIDOJO_POST_PROCESSOR_JOB_NAME, meta)
      await session.commit()
      return post_process_job.id

  post_process_job_id = loop.run_until_complete(create_post_process_job())
  post_process_apidojo_dataset.delay(post_process_job_id)

  return scraper_run.run
