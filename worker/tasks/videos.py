from uuid import UUID

from worker.main import worker_app
from worker.tasks.challenges import generate_challenges_for_topic


@worker_app.task
def process_video(job_id: UUID):
  from worker.tasks.deps import loop, video_processor, async_db
  from core.processors.jobs import create_categorize_job, create_challenge_creating_job

  processed_video = loop.run_until_complete(video_processor.run(job_id))
  categorize_job_id = loop.run_until_complete(create_categorize_job(processed_video, async_db))
  categorize_video.delay(categorize_job_id)

  challenge_creating_job_id = loop.run_until_complete(
    create_challenge_creating_job(processed_video, UUID("249b2e88-b302-11f0-bc33-7f2eac94b24a"), async_db)
  )
  generate_challenges_for_topic.delay(challenge_creating_job_id)

  return processed_video.model_dump(mode="json")


@worker_app.task
def categorize_video(job_id: UUID):
  from worker.tasks.deps import loop, topic_processor

  result = loop.run_until_complete(topic_processor.run(job_id))

  return result.model_dump(mode="json")
