from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from db.repositories.topics import TopicWithVideoCount


class CreateTopicRequest(BaseModel):
  name: str = Field(min_length=3, description="Topic name")


class TaskProcessAuthorVideos(BaseModel):
  author_id: UUID
  max_videos: int = Field(ge=1, le=100, description="Max videos ordered by uploaded_at desc")


class VideoProcessingDetails(BaseModel):
  job_id: UUID | None
  source: str
  created_at: datetime
  started_at: datetime | None
  finished_at: datetime | None
  processing_error: bool | None
  is_canceled: bool | None


class VideoProcessingStatus(BaseModel):
  id: UUID
  url: str
  created_at: datetime
  updated_at: datetime
  jobs: list[VideoProcessingDetails]

  
class UnprocessedVideos(BaseModel):
  total: int
  videos: list[VideoProcessingStatus]
  

class TotalTopics(BaseModel):
  total: int
  topics: list[TopicWithVideoCount]

