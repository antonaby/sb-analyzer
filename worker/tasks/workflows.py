from uuid import UUID

from celery import chain, group

from models.apidojo import ApidojoWorkflow
from models.videos import VideoProcessingSpec, VideoCategorizationSpec, ChallengeGenSpec, ChallengeCategorizationSpec, \
  ChallengeTranslationSpec
from worker.main import worker_app
from worker.tasks.videos import process_video, categorize_video
from worker.tasks.challenges import generate_challenges_for_video, categorize_challenge, produce_challenge_translations
from worker.tasks.apidojo import run_apidojo_actor, post_process_apidojo_dataset


@worker_app.task
def create_challenge_processing_group(challenges: dict, langs: list[str], append: bool):
  from core.processors.challenge import ChallengeProcessorResult

  challenge_gen_result = ChallengeProcessorResult(**challenges)

  tasks = []
  for challenge in challenge_gen_result.challenges:
    if challenge.is_new:
      categorize_spec = ChallengeCategorizationSpec(challenge_id=challenge.id)
      translate_challenge = ChallengeTranslationSpec(
        challenge_id=challenge.id,
        langs=langs,
        append=append
      )

      tasks.append(
        group(
          categorize_challenge.si(categorize_spec.model_dump(mode="json")),
          produce_challenge_translations.si(translate_challenge.model_dump(mode="json"))
        )
      )

  return group(tasks)()


@worker_app.task
def create_challenge_sub_workflow(video_id: UUID, pattern_group_id: UUID, langs: list[str], append: bool):
  gen_spec = ChallengeGenSpec(video_id=video_id, pattern_group_id=pattern_group_id)
  return chain(
    generate_challenges_for_video.si(gen_spec.model_dump(mode="json")),
    create_challenge_processing_group.s(langs, append)
  )()


@worker_app.task
def create_video_processing_sub_workflow(
    video_id: UUID,
    delete_downloaded_files: bool,
    pattern_group_id: UUID,
    langs: list[str],
    append: bool
):
  processing_spec = VideoProcessingSpec(video_id=video_id, delete_downloaded_files=delete_downloaded_files)
  categorization_spec = VideoCategorizationSpec(video_id=video_id)

  video_processing_chain = chain(
    process_video.si(processing_spec.model_dump(mode="json")),
    group(
      categorize_video.si(categorization_spec.model_dump(mode="json")),
      create_challenge_sub_workflow.si(video_id, pattern_group_id, langs, append)
    )
  )

  return video_processing_chain()


@worker_app.task
def create_video_processing_group(
    posts: dict,
    delete_downloaded_files: bool,
    pattern_group_id: UUID,
    langs: list[str],
    append: bool
):
  from core.processors.scraper import ApidojoPostProcessResult

  post_process_result = ApidojoPostProcessResult(**posts)
  tasks = []
  for post in post_process_result.posts:
    if post.new_video:
      tasks.append(
        create_video_processing_sub_workflow.si(post.video_id, delete_downloaded_files, pattern_group_id, langs, append)
      )

  return group(tasks)()


@worker_app.task
def transform_apidojo_actor_run(actor_run: dict) -> dict:
  from core.processors.scraper import ApidojoScraperRun
  from models.apidojo import ApidojoPostProcessorSpec

  actor_result = ApidojoScraperRun(**actor_run)
  post_processor_spec = ApidojoPostProcessorSpec(search_id=actor_result.search_id, actor_run=actor_result.run)
  return post_processor_spec.model_dump(mode="json")


@worker_app.task
def run_apidojo_workflow(apidojo_workflow: dict):
  apidojo_workflow = ApidojoWorkflow(**apidojo_workflow)

  workflow = chain(
    run_apidojo_actor.s(apidojo_workflow.actor_spec.model_dump(mode="json")),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_video_processing_group.s(
      apidojo_workflow.delete_downloaded_files,
      apidojo_workflow.pattern_group_id,
      apidojo_workflow.langs,
      apidojo_workflow.append
    )
  )

  return workflow()
