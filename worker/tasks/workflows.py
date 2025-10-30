from uuid import UUID

from celery import chain, group

from models.videos import VideoProcessingSpec, VideoCategorizationSpec, ChallengeGenSpec, ChallengeCategorizationSpec
from worker.main import worker_app
from worker.tasks.videos import process_video, categorize_video
from worker.tasks.challenges import generate_challenges_for_video, categorize_challenge
from worker.tasks.apidojo import run_apidojo_actor, post_process_apidojo_dataset


@worker_app.task
def transform_apidojo_actor_run(actor_run: dict) -> dict:
  from core.processors.scraper import ApidojoScraperRun
  from models.apidojo import ApidojoPostProcessorSpec

  actor_result = ApidojoScraperRun(**actor_run)
  post_processor_spec = ApidojoPostProcessorSpec(search_id=actor_result.search_id, actor_run=actor_result.run)
  return post_processor_spec.model_dump(mode="json")


@worker_app.task
def create_challenge_processing_group(challenges: dict):
  from core.processors.challenge import ChallengeProcessorResult

  challenge_gen_result = ChallengeProcessorResult(**challenges)

  tasks = []
  for challenge in challenge_gen_result.challenges:
    if challenge.is_new:
      categorize_spec = ChallengeCategorizationSpec(challenge_id=challenge.id)
      tasks.append(categorize_challenge.si(categorize_spec.model_dump(mode="json")))

  return group(tasks)()


@worker_app.task
def create_challenge_sub_workflow(video_id: UUID, pattern_group_id: UUID):
  gen_spec = ChallengeGenSpec(video_id=video_id, pattern_group_id=pattern_group_id)
  return chain(
    generate_challenges_for_video.si(gen_spec.model_dump(mode="json")),
    create_challenge_processing_group.s()
  )


@worker_app.task
def create_video_processing_group(posts: dict, delete_downloaded_files: bool, pattern_group_id: UUID):
  from core.processors.scraper import ApidojoPostProcessResult

  post_process_result = ApidojoPostProcessResult(**posts)
  tasks = []
  for post in post_process_result.posts:
    if post.new_video:
      processing_spec = VideoProcessingSpec(video_id=post.video_id, delete_downloaded_files=delete_downloaded_files)
      categorization_spec = VideoCategorizationSpec(video_id=post.video_id)

      video_processing_chain = chain(
        process_video.si(processing_spec.model_dump(mode="json")),
        group(
          categorize_video.si(categorization_spec.model_dump(mode="json")),
          create_challenge_sub_workflow(post.video_id, pattern_group_id)
        )
      )

      tasks.append(video_processing_chain)

  return group(tasks)()


@worker_app.task
def run_apidojo_workflow(apidojo_spec: dict):
  workflow = chain(
    run_apidojo_actor.s(apidojo_spec),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_video_processing_group.s(True, UUID("249b2e88-b302-11f0-bc33-7f2eac94b24a"))
  )

  return workflow()
