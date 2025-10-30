from uuid import UUID

from models.videos import VideoProcessingSpec, VideoCategorizationSpec
from worker.main import worker_app


@worker_app.task
def process_video(spec: dict):
  from worker.tasks.deps import loop, video_processor

  processor_spec = VideoProcessingSpec(**spec)
  processed_video = loop.run_until_complete(video_processor.run(processor_spec))

  return processed_video.model_dump(mode="json")


@worker_app.task
def categorize_video(spec: dict):
  from worker.tasks.deps import loop, topic_processor

  topic_spec = VideoCategorizationSpec(**spec)
  result = loop.run_until_complete(topic_processor.run(topic_spec))

  return result.model_dump(mode="json")
