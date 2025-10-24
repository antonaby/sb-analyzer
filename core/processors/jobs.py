from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.challenge import CreatedChallenge
from core.processors.common import SavedPost
from core.processors.scraper import ApidojoScraperRun
from core.processors.video import ProcessedVideo, AssignedTopic
from db.repositories.jobs import JobRepository, ApidojoPostProcessorJob, APIDOJO_POST_PROCESSOR_JOB_NAME, \
  ProcessVideoJob, PROCESS_VIDEO_JOB_NAME, CategorizationVideoJob, CATEGORIZATION_VIDEO_JOB_NAME, TranslationJob, \
  CHALLENGE_TRANSLATION_JOB_NAME, TOPIC_TRANSLATION_JOB_NAME, CHALLENGE_GEN_JOB_NAME, ChallengeGenJob
from db.repositories.topics import TopicRepository


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
    meta = CategorizationVideoJob(
      video_id=video.video_id
    )
    post_process_job = await job_repo.create_job(CATEGORIZATION_VIDEO_JOB_NAME, meta)
    await session.commit()
    return post_process_job.id


async def create_challenge_translation_jobs(challenges: list[CreatedChallenge], db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)
    job_ids: list[UUID] = []

    for challenge in challenges:
      job_meta = TranslationJob(target_id=challenge.id, langs=["ru", "fr", "de"])
      job = await job_repo.create_job(CHALLENGE_TRANSLATION_JOB_NAME, job_meta)
      job_ids.append(job.id)

    await session.commit()
    return job_ids


async def create_challenge_gen_jobs(db: async_sessionmaker[AsyncSession]) -> list[UUID]:
  async with db() as session:
    job_repo = JobRepository(session)
    topic_repo = TopicRepository(session)
    topics = await topic_repo.find_topics_without_challenges(min_videos=40)

    job_ids: list[UUID] = []
    for topic in topics:
      job_meta = ChallengeGenJob(topic_id=topic.id)
      job = await job_repo.create_job(CHALLENGE_GEN_JOB_NAME, job_meta)
      job_ids.append(job.id)


    await session.commit()
    return job_ids
