from celery import chain, group

from models.videos import VideoProcessingSpec, VideoCategorizationSpec
from worker.main import worker_app
from worker.tasks.videos import process_video, categorize_video
from worker.tasks.apidojo import run_apidojo_actor, post_process_apidojo_dataset


@worker_app.task
def transform_apidojo_actor_run(actor_run: dict) -> dict:
  from core.processors.scraper import ApidojoScraperRun
  from models.apidojo import ApidojoPostProcessorSpec

  actor_result = ApidojoScraperRun(**actor_run)
  post_processor_spec = ApidojoPostProcessorSpec(search_id=actor_result.search_id, actor_run=actor_result.run)
  return post_processor_spec.model_dump(mode="json")


@worker_app.task
def create_video_processing_group(posts: dict, delete_downloaded_files: bool):
  from core.processors.scraper import ApidojoPostProcessResult

  post_process_result = ApidojoPostProcessResult(**posts)
  tasks = []
  for post in post_process_result.posts:
    if post.new_video:
      processing_spec = VideoProcessingSpec(video_id=post.video_id, delete_downloaded_files=delete_downloaded_files)
      categorization_spec = VideoCategorizationSpec(video_id=post.video_id)

      video_processing_chain = chain(
        process_video.si(processing_spec.model_dump(mode="json")),
        categorize_video.si(categorization_spec.model_dump(mode="json"))
      )

      tasks.append(video_processing_chain)

  return group(tasks)()


@worker_app.task
def run_apidojo_workflow(apidojo_spec: dict):
  workflow = chain(
    run_apidojo_actor.s(apidojo_spec),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_video_processing_group.s(True)
  )

  return workflow()
