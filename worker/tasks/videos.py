from celery import group

from models.videos import VideoProcessingSpec, VideoCategorizationSpec, VideoDownloadSpec, VideoBatchProcessingSpec
from worker.main import worker_app


@worker_app.task
def download_video(spec: dict):
  from worker.tasks.deps import loop, video_download_processor

  processor_spec = VideoDownloadSpec(**spec)
  processed_video = loop.run_until_complete(video_download_processor.run(processor_spec))

  return processed_video.model_dump(mode="json")


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


@worker_app.task
def batch_process_videos(spec: dict):
  from worker.tasks.deps import loop, async_db
  from core.processors.video import find_unprocessed_videos

  processor_spec = VideoBatchProcessingSpec(**spec)
  video_ids = loop.run_until_complete(find_unprocessed_videos(async_db, processor_spec.limit))

  tasks = []
  for video_id in video_ids:
    video_spec = VideoProcessingSpec(video_id=video_id, delete_downloaded_files=processor_spec.delete_downloaded_files)
    tasks.append(
      process_video.si(video_spec.model_dump(mode="json"))
    )

  group_task = group(tasks)
  return group_task()
