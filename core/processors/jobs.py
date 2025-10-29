from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.challenge import ChallengeDetails
from core.processors.common import SavedPost
from core.processors.scraper import ApidojoScraperRun
from core.processors.video import ProcessedVideo
from db.models import Challenge, Job
from db.repositories.jobs import JobRepository, ApidojoPostProcessorJob, APIDOJO_POST_PROCESSOR_JOB_NAME, \
  ProcessVideoJob, PROCESS_VIDEO_JOB_NAME, VideoCategorizationJob, VIDEO_CATEGORIZATION_JOB_NAME, TranslationJob, \
  CHALLENGE_TRANSLATION_JOB_NAME, ChallengeGenJob, CHALLENGE_GEN_JOB_NAME, ChallengeCategorizationJob, \
  CHALLENGE_CATEGORIZATION_JOB_NAME, APIDOJO_SCRAPER_NAME, APIDOJO_SCRAPER_JOB_NAME


class ScraperJobProcessorResult(BaseModel):
  jobs: dict[str, list[UUID]]


class ScraperJobProcessor:

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker

  async def run(self) -> ScraperJobProcessorResult:
    jobs: dict[str, list[UUID]] = {}

    async with self._db() as session:
      job_repo = JobRepository(session)
      apidojo_jobs = await self._process_apidojo_jobs(job_repo)
      jobs[APIDOJO_SCRAPER_NAME] = [j.id for j in apidojo_jobs]

      await job_repo.commit()

    return ScraperJobProcessorResult(jobs=jobs)

  @staticmethod
  async def _process_apidojo_jobs(repo: JobRepository) -> list[Job]:
    scraper_jobs = await repo.get_scraper_jobs(APIDOJO_SCRAPER_NAME)
    exec_jobs: list[Job] = []

    for scraper_job in scraper_jobs:
      exec_job = await repo.create_job(APIDOJO_SCRAPER_JOB_NAME, scraper_job.meta)
      exec_jobs.append(exec_job)
      scraper_job.last_job_id = exec_job.id

    return exec_jobs


async def create_apidojo_post_process_job(scraper_run: ApidojoScraperRun, db: async_sessionmaker[AsyncSession]) -> UUID:
  async with db() as session:
    job_repo = JobRepository(session)
    meta = ApidojoPostProcessorJob(
      search_id=scraper_run.search_id, default_dataset_id=scraper_run.run["defaultDatasetId"]
    )
    post_process_job = await job_repo.create_job(APIDOJO_POST_PROCESSOR_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id


async def create_video_processing_jobs(posts: list[SavedPost], db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)
    job_ids: list[UUID] = []

    for post in posts:
      if post.new_video:
        process_job_meta = ProcessVideoJob(video_id=post.video_id, delete_downloaded_files=True)
        job = await job_repo.create_job(PROCESS_VIDEO_JOB_NAME, process_job_meta)
        job_ids.append(job.id)

    await session.commit()
    return job_ids


async def create_categorize_job(video: ProcessedVideo, db: async_sessionmaker[AsyncSession]) -> UUID:
  async with db() as session:
    job_repo = JobRepository(session)
    meta = VideoCategorizationJob(
      video_id=video.video_id
    )
    post_process_job = await job_repo.create_job(VIDEO_CATEGORIZATION_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id


async def create_challenge_creating_job(video: ProcessedVideo, pattern_group_id: UUID, db: async_sessionmaker[AsyncSession]) -> UUID:
  async with db() as session:
    job_repo = JobRepository(session)
    meta = ChallengeGenJob(
      video_id=video.video_id,
      pattern_group_id=pattern_group_id
    )
    post_process_job = await job_repo.create_job(CHALLENGE_GEN_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id


async def create_challenge_translation_jobs(challenges: list[ChallengeDetails], db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)
    job_ids: list[UUID] = []

    for challenge in challenges:
      if challenge.is_new:
        job_meta = TranslationJob(target_id=challenge.id, langs=["ru", "fr", "de"], append=True)
        job = await job_repo.create_job(CHALLENGE_TRANSLATION_JOB_NAME, job_meta)
        job_ids.append(job.id)

    await session.commit()
    return job_ids


async def create_challenge_categorization_jobs(challenges: list[ChallengeDetails], db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)
    job_ids: list[UUID] = []

    for challenge in challenges:
      if challenge.is_new:
        job_meta = ChallengeCategorizationJob(challenge_id=challenge.id)
        job = await job_repo.create_job(CHALLENGE_CATEGORIZATION_JOB_NAME, job_meta)
        job_ids.append(job.id)

    await session.commit()
    return job_ids


async def adhoc_create_categorize_all_challenges_jobs(db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)

    stmt = select(Challenge).where(
      Challenge.categorized_at.is_(None) | Challenge.categorization_error.is_(True)
    )

    rows = await session.execute(stmt)
    challenges = rows.scalars().all()

    job_ids: list[UUID] = []
    for challenge in challenges:
      job_meta = ChallengeCategorizationJob(challenge_id=challenge.id)
      job = await job_repo.create_job(CHALLENGE_CATEGORIZATION_JOB_NAME, job_meta)
      job_ids.append(job.id)

    await session.commit()
    return job_ids
