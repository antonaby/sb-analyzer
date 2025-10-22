from uuid import UUID

from worker.main import worker_app


@worker_app.task
def generate_challenges_for_topic(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, challenge_processor

  result = loop.run_until_complete(challenge_processor.run(job_id))
  return result.model_dump(mode="json")


@worker_app.task
def produce_challenge_translations(job_id: UUID) -> dict:
  from worker.tasks.deps import loop, translation_processor

  result = loop.run_until_complete(translation_processor.run(job_id))
  return result.model_dump(mode="json")

