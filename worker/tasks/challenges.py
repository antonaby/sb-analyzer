from uuid import UUID

from models.videos import ChallengeGenSpec, ChallengeCategorizationSpec, ChallengeTranslationSpec
from worker.main import worker_app


@worker_app.task
def generate_challenges_for_video(spec: dict, video_processing_id: UUID | None = None) -> dict:
  from worker.tasks.deps import loop, challenge_processor

  challenge_gen_spec = ChallengeGenSpec(**spec)
  if video_processing_id:
    coro = challenge_processor.run_workflow(challenge_gen_spec, video_processing_id)
  else:
    coro = challenge_processor.run(challenge_gen_spec)

  result = loop.run_until_complete(coro)

  return result.model_dump(mode="json")


@worker_app.task
def categorize_challenge(spec: dict) -> dict:
  from worker.tasks.deps import loop, challenge_category_processor

  challenge_category_spec = ChallengeCategorizationSpec(**spec)
  result = loop.run_until_complete(challenge_category_processor.run(challenge_category_spec))
  return result.model_dump(mode="json")


@worker_app.task
def produce_challenge_translations(spec: dict) -> dict:
  from worker.tasks.deps import loop, challenge_translation_processor

  challenge_translation_spec = ChallengeTranslationSpec(**spec)
  result = loop.run_until_complete(challenge_translation_processor.run(challenge_translation_spec))
  return result.model_dump(mode="json")
