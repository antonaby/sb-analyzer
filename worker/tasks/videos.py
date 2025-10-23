from uuid import UUID

from celery import group

from worker.main import worker_app


@worker_app.task
def process_video(job_id: UUID):
  from worker.tasks.deps import loop, video_processor, async_db
  from core.processors.jobs import create_categorize_job

  processed_video = loop.run_until_complete(video_processor.run(job_id))
  post_process_job_id = loop.run_until_complete(create_categorize_job(processed_video, async_db))
  categorize_video.delay(post_process_job_id)

  return processed_video.model_dump(mode="json")


@worker_app.task
def categorize_video(job_id: UUID):
  from worker.tasks.deps import loop, topic_processor, async_db
  from core.processors.jobs import create_topic_translation_jobs

  result = loop.run_until_complete(topic_processor.run(job_id))
  job_ids = loop.run_until_complete(create_topic_translation_jobs(result.topics, async_db))

  if len(job_ids) > 0:
    tasks = [translate_topic.s(job_id) for job_id in job_ids]
    processing_job = group(tasks)
    processing_job.apply_async()

  return result.model_dump(mode="json")


@worker_app.task
def translate_topic(job_id: UUID):
  from worker.tasks.deps import loop, topic_translation_processor

  result = loop.run_until_complete(topic_translation_processor.run(job_id))
  return result.model_dump(mode="json")
