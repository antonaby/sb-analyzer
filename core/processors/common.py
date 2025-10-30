from abc import ABC
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from db.models import VideoSource


class AuthorDetails(BaseModel):
  url: str
  author_from: VideoSource
  verified: bool | None
  followers: int | None
  total_videos: int | None


class PostDetails(BaseModel):
  search_id: UUID
  url: str
  download_url: str
  post_from: VideoSource
  title: str
  description: str
  hashtags: list[str]
  uploaded_at: datetime
  likes: int
  views: int
  comments: int
  scraper: str
  source: dict


class ScrapedVideo(BaseModel):
  post: PostDetails
  author: AuthorDetails


class JobProcessorError(Exception):
  pass


class JobProcessor(ABC):

  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker


class SavedPost(BaseModel):
  author_id: UUID
  new_author: bool
  video_id: UUID
  new_video: bool


class CreatedTranslation(BaseModel):
  id: UUID
  land: str
  text: str
