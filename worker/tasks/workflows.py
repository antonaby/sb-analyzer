from celery import chain

from worker.main import worker_app
from worker.tasks.apidojo import run_apidojo_actor, post_process_apidojo_dataset


@worker_app.task
def transform_apidojo_actor_run(actor_run: dict) -> dict:
  from core.processors.scraper import ApidojoScraperRun
  from models.apidojo import ApidojoPostProcessorSpec

  actor_result = ApidojoScraperRun(**actor_run)
  post_processor_spec = ApidojoPostProcessorSpec(search_id=actor_result.search_id, actor_run=actor_result.run)
  return post_processor_spec.model_dump(mode="json")


@worker_app.task
def run_apidojo_workflow(apidojo_spec: dict):
  workflow = chain(
    run_apidojo_actor.s(apidojo_spec),
    transform_apidojo_actor_run.s(),
    post_process_apidojo_dataset.s()
  )

  workflow.apply_async()
