from uuid import UUID

from pydantic import BaseModel

from models.common import BaseWorkflowSpec


class VideoDownloadSpec(BaseModel):
  video_id: UUID


class VideoProcessingSpec(BaseModel):
  video_id: UUID
  video_processing_id: UUID
  delete_downloaded_files: bool


class VideoBatchProcessingSpec(BaseWorkflowSpec):
  limit: int


class VideoCategorizationSpec(BaseModel):
  video_id: UUID
  video_processing_id: UUID
  topic_group_id: UUID


class ChallengeGenSpec(BaseModel):
  video_id: UUID
  video_processing_id: UUID
  pattern_group_id: UUID


class ChallengeCategorizationSpec(BaseModel):
  challenge_id: UUID
  topic_group_id: UUID


class ChallengeTranslationSpec(BaseModel):
  challenge_id: UUID
  langs: list[str]
  append: bool


class VideoProcessingWorkflow(BaseWorkflowSpec):
  video_id: UUID
  video_processing_id: UUID
