from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from db.models import VideoProcessingKind, VideoProcessing
from db.repositories.videos import VideoRepository
from models.processing import VideoProcessingPipline


class PipelineProcessorError(Exception):
  pass


class PipelineProcessor:

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker

  async def create_pipeline(
      self,
      video_id: UUID,
      summarize: bool = True,
      categorize: bool = True,
      delete_downloaded_files: bool = True
  ) -> VideoProcessingPipline:
    async with self._db() as session:
      repo = VideoRepository(session)
      await repo.invalidate_old_video_processing(video_id)

      summarization_job: VideoProcessing | None = None
      categorization_job: VideoProcessing | None = None

      if summarize:
        summarization_job = await repo.create_video_processing(video_id, VideoProcessingKind.summarizing)

      if categorize:
        categorization_job = await repo.create_video_processing(video_id, VideoProcessingKind.categorization)

      await session.commit()

      return {
        "summarizing_job_id": summarization_job.id if summarization_job else None,
        "categorization_job_id": categorization_job.id if categorization_job else None,
        "delete_downloaded_files": delete_downloaded_files
      }

  async def set_celery_job_id(self, job_id: UUID, celery_job_id: UUID):
    async with self._db() as session:
      job = await session.get(VideoProcessing, job_id)
      if not job:
        raise PipelineProcessorError(f"Job {job_id} not found")

      job.job_id = celery_job_id
      await session.commit()
