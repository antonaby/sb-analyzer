from uuid import UUID

from celery import group

from apify.actor import ActorRun
from worker.main import worker_app


@worker_app.task
def save_post(job_id: UUID):
  from worker.tasks.deps import loop, post_detail_processor

  saved_post = loop.run_until_complete(post_detail_processor.run(job_id))
  return saved_post.model_dump(mode="json")


@worker_app.task
def run_apidojo_scraper(job_id: UUID) -> ActorRun:
  from db.repositories.jobs import JobRepository, POST_DETAILS_JOB_NAME, PostDetailsJob
  from worker.tasks.deps import loop, apidojo_processor, async_db

  scraper_run = loop.run_until_complete(apidojo_processor.run(job_id))

  async def create_save_post_tasks():
    tasks = []

    async with async_db() as session:
      job_repo = JobRepository(session)

      for video in scraper_run.videos:
        meta = PostDetailsJob(
          scraper="apidojo",
          post=video.post.model_dump(mode="json"),
          author=video.author.model_dump(mode="json")
        )
        job = await job_repo.create_job(POST_DETAILS_JOB_NAME, meta.model_dump(mode="json"))

        tasks.append(save_post.s(job.id))

      await session.commit()

    return tasks

  save_tasks = loop.run_until_complete(create_save_post_tasks())
  save_task_group = group(save_tasks)
  save_task_group.apply_async()

  return scraper_run.run
