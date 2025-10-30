from celery import chain, group

from models.videos import VideoProcessingSpec
from worker.main import worker_app
from worker.tasks.videos import process_video
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
      spec = VideoProcessingSpec(video_id=post.video_id, delete_downloaded_files=delete_downloaded_files)
      tasks.append(process_video.s(spec.model_dump(mode="json")))

  return group(tasks)()


@worker_app.task
def run_apidojo_workflow(apidojo_spec: dict):
  workflow = chain(
    run_apidojo_actor.s(apidojo_spec),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_video_processing_group.s(True)
  )

  workflow.apply_async()
