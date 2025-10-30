from uuid import UUID

from pydantic import BaseModel


class VideoProcessingSpec(BaseModel):
  video_id: UUID
  delete_downloaded_files: bool


class VideoCategorizationSpec(BaseModel):
  video_id: UUID
