from uuid import UUID

from worker.main import worker_app


@worker_app.task
def generate_challenges_for_topic(topic_id: UUID) -> dict:
  from worker.tasks.deps import loop, challenge_processor

  result = loop.run_until_complete(challenge_processor.create_challenges(topic_id))
  return result.model_dump(mode="json")
