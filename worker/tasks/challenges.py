from uuid import UUID

from celery import group

from worker.main import worker_app


@worker_app.task
def generate_challenges_for_topic(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, challenge_processor, async_db
  from worker.tasks.helpers import create_challenge_translation_jobs

  result = loop.run_until_complete(challenge_processor.run(job_id))
  job_ids = loop.run_until_complete(create_challenge_translation_jobs(result.challenges, async_db))

  if len(job_ids) > 0:
    tasks = [produce_challenge_translations.s(job_id) for job_id in job_ids]
    processing_job = group(tasks)
    processing_job.apply_async()

  return result.model_dump(mode="json")


@worker_app.task
def produce_challenge_translations(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, translation_processor

  result = loop.run_until_complete(translation_processor.run(job_id))
  return result.model_dump(mode="json")

