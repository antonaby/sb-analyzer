from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.common import JobProcessor, SavedPost
from db.models import Workflow, VideoProcessing
from db.repositories.videos import VideoRepository
from models.videos import VideoProcessingWorkflow


class WorkflowProcessorResult(BaseModel):
  workflow_id: UUID
  video_processing_workflows: list[VideoProcessingWorkflow]


class WorkflowProcessor(JobProcessor):

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
  
  async def run(
      self,
      topic_group_id: UUID,
      pattern_group_id: UUID,
      posts: list[SavedPost],
      delete_downloaded_files: bool,
      langs: list[str],
      append: bool,
      only_new: bool = True,
  ) -> WorkflowProcessorResult:
    async with self._db() as session:
      video_repo = VideoRepository(session)
      workflow = await video_repo.create_workflow(topic_group_id, pattern_group_id)

      video_workflows: list[VideoProcessingWorkflow] = []
      for post in posts:
        if (only_new and post.new_video) or not only_new:
          video_processing = await video_repo.create_video_processing(workflow.id, post.video_id)
          video_workflow = VideoProcessingWorkflow(
            video_id=post.video_id,
            video_processing_id=video_processing.id,
            delete_downloaded_files=delete_downloaded_files,
            pattern_group_id=pattern_group_id,
            topic_group_id=topic_group_id,
            langs=langs,
            append=append
          )
          video_workflows.append(video_workflow)

      await session.commit()

      return WorkflowProcessorResult(
        workflow_id=workflow.id,
        video_processing_workflows=video_workflows
      )
