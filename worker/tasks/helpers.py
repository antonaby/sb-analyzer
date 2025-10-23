from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.scraper import ApidojoScraperRun
from core.processors.video import ProcessedVideo
from db.repositories.jobs import JobRepository, ApidojoPostProcessorJob, APIDOJO_POST_PROCESSOR_JOB_NAME, \
  CategorizationVideoJob, CATEGORIZATION_VIDEO_JOB_NAME


async def create_apidojo_post_process_job(scraper_run: ApidojoScraperRun, db: async_sessionmaker[AsyncSession]) -> UUID:
  async with db() as session:
    job_repo = JobRepository(session)
    meta = ApidojoPostProcessorJob(
      search_id=scraper_run.search_id, default_dataset_id=scraper_run.run["defaultDatasetId"]
    )
    post_process_job = await job_repo.create_job(APIDOJO_POST_PROCESSOR_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id


async def create_categorize_job(video: ProcessedVideo, db: async_sessionmaker[AsyncSession]) -> UUID:
  async with db() as session:
    job_repo = JobRepository(session)
    meta = CategorizationVideoJob(
      video_id=video.video_id
    )
    post_process_job = await job_repo.create_job(CATEGORIZATION_VIDEO_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id
