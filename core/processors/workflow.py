from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.processors.common import JobProcessor, SavedPost
from db.repositories.videos import VideoRepository
from models.common import BaseWorkflowSpec
from models.videos import VideoProcessingWorkflow


class WorkflowProcessorResult(BaseModel):
  workflow_id: UUID
  video_processing_workflows: list[VideoProcessingWorkflow]


class WorkflowProcessor(JobProcessor):

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)

  async def process_posts(
      self,
      posts: list[SavedPost],
      workflow_spec: BaseWorkflowSpec,
      only_new: bool
  ) -> WorkflowProcessorResult:
    video_ids = [post.video_id for post in posts if (only_new and post.new_video) or not only_new]
    async with self._db() as session:
      video_repo = VideoRepository(session)
      workflows = await self._create_video_workflows(video_ids, workflow_spec, video_repo)
      await session.commit()

      return workflows

  async def process_unprocessed_videos(self, limit: int, workflow_spec: BaseWorkflowSpec):
    async with self._db() as session:
      video_repo = VideoRepository(session)
      videos = await video_repo.find_unprocessed_videos(limit)
      video_ids = [v.id for v in videos]
      workflows = await self._create_video_workflows(video_ids, workflow_spec, video_repo)
      await session.commit()

      return workflows

  @staticmethod
  async def _create_video_workflows(
      video_ids: list[UUID],
      workflow_spec: BaseWorkflowSpec,
      video_repo: VideoRepository
  ) -> WorkflowProcessorResult:
    workflow = await video_repo.create_workflow(workflow_spec.topic_group_id, workflow_spec.pattern_group_id)

    video_workflows: list[VideoProcessingWorkflow] = []
    for video_id in video_ids:
      video_processing = await video_repo.create_video_processing(workflow.id, video_id)
      video_workflow = VideoProcessingWorkflow(
        video_id=video_id,
        video_processing_id=video_processing.id,
        **workflow_spec.model_dump()
      )
      video_workflows.append(video_workflow)

    return WorkflowProcessorResult(
      workflow_id=workflow.id,
      video_processing_workflows=video_workflows
    )
