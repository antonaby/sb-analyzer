from typing import TypedDict

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class AuthorDetails(TypedDict):
  url: str
  author_from: str
  verified: bool | None
  followers: int | None
  total_videos: int | None


class PostDetails(TypedDict):
  search_id: str
  url: str
  download_url: str
  post_from: str
  title: str
  description: str
  hashtags: list[str]
  uploaded_at_iso: str
  likes: int
  views: int
  comments: int
  scraper: str
  source: dict


class TopicData(TypedDict):
  id: UUID
  name: str


class VideoData(TypedDict):
  video_id: UUID
  source: str
  title: str
  description: str
  uploaded_at_iso: datetime
  likes: int
  views: int
  comments: int
  hashtags: list[str]
  meta_summary: list[str]
  meta_summary_video_type: list[str]
  summary: str
  summary_synopsis: list[str]
  transcription: list[str]
