from uuid import UUID

from pydantic import BaseModel


class VideoDownloadSpec(BaseModel):
  video_id: UUID


class VideoProcessingSpec(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool


class VideoBatchProcessingSpec(BaseModel):
  limit: int
  delete_downloaded_files: bool


class VideoCategorizationSpec(BaseModel):
  video_id: UUID
  topic_group_id: UUID


class ChallengeGenSpec(BaseModel):
  video_id: UUID
  pattern_group_id: UUID


class ChallengeCategorizationSpec(BaseModel):
  challenge_id: UUID
  topic_group_id: UUID


class ChallengeTranslationSpec(BaseModel):
  challenge_id: UUID
  langs: list[str]
  append: bool


class VideoProcessingWorkflow(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool
  pattern_group_id: UUID
  topic_group_id: UUID
  langs: list[str]
  append: bool
