from typing import TypedDict

from datetime import datetime
from pydantic import BaseModel


class AuthorDetails(TypedDict):
  url: str
  author_from: str
  verified: bool | None
  followers: int | None
  total_videos: int | None


class PostDetails(TypedDict):
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
  

class VideoSummary(BaseModel):
  main_idea: str
  theme: list[str]
  video_type: list[str]
  synopsis: list[str]
