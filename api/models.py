from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from db.models import VideoProcessingKind, VideoSource
from models.apidojo import DateRange, SortType


class CreateTopicRequest(BaseModel):
  name: str = Field(min_length=3, description="Topic name")


class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


class ApidojoCollectUrls(BaseModel):
  urls: list[str] = Field(min_length=1, description="At least one url")
  max_items: int


class TaskProcessAuthorVideos(BaseModel):
  author_id: UUID
  max_videos: int = Field(ge=1, le=100, description="Max videos ordered by uploaded_at desc")


class VideoProcessingDetails(BaseModel):
  job_id: UUID | None
  source: VideoProcessingKind
  created_at: datetime
  started_at: datetime | None
  finished_at: datetime | None


class VideoProcessingStatus(BaseModel):
  id: UUID
  url: str
  jobs: list[VideoProcessingDetails]

  
class UnprocessedVideos(BaseModel):
  total: int
  videos: list[VideoProcessingStatus]
  

class TopicsShort(BaseModel):
  id: UUID
  name: str
  total_videos: int
  

class TotalTopics(BaseModel):
  total: int
  topics: list[TopicsShort]


class AuthorDetails(BaseModel):
  id: UUID
  url: str
  source: VideoSource
  verified: bool | None
  followers: int | None
  total_videos: int | None
  is_reviewed: bool
  created_at: datetime
  updated_at: datetime
