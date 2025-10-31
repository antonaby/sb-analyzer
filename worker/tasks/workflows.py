from uuid import UUID

from celery import chain, group

from models.apidojo import ApidojoWorkflow, ApidojoDownloadWorkflow
from models.videos import VideoProcessingSpec, VideoCategorizationSpec, ChallengeGenSpec, ChallengeCategorizationSpec, \
  ChallengeTranslationSpec, VideoProcessingWorkflow, VideoDownloadSpec, VideoBatchProcessingSpec
from worker.main import worker_app
from worker.tasks.videos import process_video, categorize_video, download_video
from worker.tasks.challenges import generate_challenges_for_video, categorize_challenge, produce_challenge_translations
from worker.tasks.apidojo import run_apidojo_actor, post_process_apidojo_dataset


@worker_app.task
def create_challenge_processing_group(challenges: dict, topic_group_id: UUID, langs: list[str], append: bool):
  from core.processors.challenge import ChallengeProcessorResult

  challenge_gen_result = ChallengeProcessorResult(**challenges)

  tasks = []
  for challenge in challenge_gen_result.challenges:
    if challenge.is_new:
      categorize_spec = ChallengeCategorizationSpec(challenge_id=challenge.id, topic_group_id=topic_group_id)
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
def create_challenge_sub_workflow(workflow: dict):
  video_workflow = VideoProcessingWorkflow(**workflow)

  gen_spec = ChallengeGenSpec(
    video_id=video_workflow.video_id,
    pattern_group_id=video_workflow.pattern_group_id
  )
  return chain(
    generate_challenges_for_video.si(gen_spec.model_dump(mode="json")),
    create_challenge_processing_group.s(
      video_workflow.topic_group_id,
      video_workflow.langs,
      video_workflow.append
    )
  )()


@worker_app.task
def run_video_processing_workflow(workflow: dict):
  video_workflow = VideoProcessingWorkflow(**workflow)

  processing_spec = VideoProcessingSpec(
    video_id=video_workflow.video_id,
    delete_downloaded_files=video_workflow.delete_downloaded_files
  )
  categorization_spec = VideoCategorizationSpec(
    video_id=video_workflow.video_id,
    topic_group_id=video_workflow.topic_group_id
  )

  video_processing_chain = chain(
    process_video.si(processing_spec.model_dump(mode="json")),
    group(
      categorize_video.si(categorization_spec.model_dump(mode="json")),
      create_challenge_sub_workflow.si(workflow)
    )
  )

  return video_processing_chain()


@worker_app.task
def create_apidojo_video_processing_group(
    posts: dict,
    workflow: dict
):
  from core.processors.scraper import ApidojoPostProcessResult

  post_process_result = ApidojoPostProcessResult(**posts)
  apidojo_workflow = ApidojoWorkflow(**workflow)

  tasks = []
  for post in post_process_result.posts:
    if post.new_video:
      video_workflow = VideoProcessingWorkflow(
        video_id=post.video_id,
        delete_downloaded_files=apidojo_workflow.delete_downloaded_files,
        pattern_group_id=apidojo_workflow.pattern_group_id,
        topic_group_id=apidojo_workflow.topic_group_id,
        langs=apidojo_workflow.langs,
        append=apidojo_workflow.append
      )

      tasks.append(
        run_video_processing_workflow.si(video_workflow.model_dump(mode="json"))
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
def run_apidojo_workflow(workflow: dict):
  apidojo_workflow = ApidojoWorkflow(**workflow)

  workflow_task = chain(
    run_apidojo_actor.s(apidojo_workflow.actor_spec.model_dump(mode="json")),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_apidojo_video_processing_group.s(workflow)
  )

  return workflow_task()


@worker_app.task
def create_video_download_group(posts: dict):
  from core.processors.scraper import ApidojoPostProcessResult

  post_process_result = ApidojoPostProcessResult(**posts)

  tasks = []
  for post in post_process_result.posts:
    if post.new_video:
      spec = VideoDownloadSpec(video_id=post.video_id)
      tasks.append(
        download_video.si(spec.model_dump(mode="json"))
      )

  return group(tasks)()


@worker_app.task
def run_apidojo_download_workflow(workflow: dict):
  apidojo_workflow = ApidojoDownloadWorkflow(**workflow)

  workflow_task = chain(
    run_apidojo_actor.s(apidojo_workflow.actor_spec.model_dump(mode="json")),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s(),
    create_video_download_group.s()
  )

  return workflow_task()


@worker_app.task
def batch_process_videos(spec: dict):
  from worker.tasks.deps import loop, async_db
  from core.processors.video import find_unprocessed_videos

  processor_spec = VideoBatchProcessingSpec(**spec)
  video_ids = loop.run_until_complete(find_unprocessed_videos(async_db, processor_spec.limit))

  tasks = []
  for video_id in video_ids:
    video_spec = VideoProcessingWorkflow(
      video_id=video_id,
      delete_downloaded_files=processor_spec.delete_downloaded_files,
      pattern_group_id=processor_spec.pattern_group_id,
      topic_group_id=processor_spec.topic_group_id,
      langs=processor_spec.langs,
      append=processor_spec.append
    )
    tasks.append(
      run_video_processing_workflow.si(video_spec.model_dump(mode="json"))
    )

  group_task = group(tasks)
  return group_task()
