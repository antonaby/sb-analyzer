from uuid import UUID

from pydantic import BaseModel


class VideoProcessingSpec(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool


class VideoCategorizationSpec(BaseModel):
  video_id: UUID


class ChallengeGenSpec(BaseModel):
  video_id: UUID
  pattern_group_id: UUID


class ChallengeCategorizationSpec(BaseModel):
  challenge_id: UUID
