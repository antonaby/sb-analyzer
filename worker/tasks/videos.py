from uuid import UUID

from worker.main import worker_app


@worker_app.task
def process_video(job_id: UUID):
  from worker.tasks.deps import loop, video_processor

  processed_video = loop.run_until_complete(video_processor.run(job_id))
  return processed_video.model_dump(mode="json")


@worker_app.task
def categorize_video(job_id: UUID):
  from worker.tasks.deps import loop, topic_processor

  topics = loop.run_until_complete(topic_processor.run(job_id))
  return topics.model_dump(mode="json")
