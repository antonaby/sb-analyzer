from uuid import UUID

from celery import group

from models.videos import ChallengeGenSpec, ChallengeCategorizationSpec
from worker.main import worker_app


@worker_app.task
def generate_challenges_for_video(spec: dict) -> dict:
  from worker.tasks.deps import loop, challenge_processor

  challenge_gen_spec = ChallengeGenSpec(**spec)
  result = loop.run_until_complete(challenge_processor.run(challenge_gen_spec))

  return result.model_dump(mode="json")


@worker_app.task
def categorize_challenge(spec: dict) -> dict:
  from worker.tasks.deps import loop, challenge_category_processor

  challenge_category_spec = ChallengeCategorizationSpec(**spec)
  result = loop.run_until_complete(challenge_category_processor.run(challenge_category_spec))
  return result.model_dump(mode="json")






@worker_app.task
def produce_challenge_translations(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, challenge_translation_processor

  result = loop.run_until_complete(challenge_translation_processor.run(job_id))
  return result.model_dump(mode="json")





@worker_app.task
def adhoc_categorize_all_challenges() -> dict:
  from worker.tasks.deps import loop, async_db
  from core.processors.jobs import adhoc_create_categorize_all_challenges_jobs

  job_ids = loop.run_until_complete(adhoc_create_categorize_all_challenges_jobs(async_db))
  if len(job_ids) > 0:
    tasks = [categorize_challenge.s(job_id) for job_id in job_ids]
    c_processing_job = group(tasks)
    c_processing_job.apply_async()

  return {
    "total_jobs": len(job_ids)
  }
