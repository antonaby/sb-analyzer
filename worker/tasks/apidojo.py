from models.apidojo import ApidojoActorSpec, ApidojoPostProcessorSpec
from worker.main import worker_app


@worker_app.task
def post_process_apidojo_dataset(spec: dict) -> dict:
  from worker.tasks.deps import loop, apidojo_post_processor

  apidojo_spec = ApidojoPostProcessorSpec(**spec)
  saved_posts = loop.run_until_complete(apidojo_post_processor.run(apidojo_spec))
  return saved_posts.model_dump(mode="json")


@worker_app.task
def run_apidojo_actor(spec: dict) -> dict:
  from worker.tasks.deps import loop, apidojo_processor

  apidojo_spec = ApidojoActorSpec(**spec)
  result = loop.run_until_complete(apidojo_processor.run(apidojo_spec))

  return result.model_dump(mode="json")
