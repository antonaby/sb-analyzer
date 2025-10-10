from typing import TypedDict

from pydantic import BaseModel


class AuthorDetails(TypedDict):
  url: str
  author_from: str


class PostDetails(TypedDict):
  url: str
  download_url: str
  post_from: str
  title: str
  description: str
  hashtags: list[str]
  scraper: str
  source: dict
  

class VideoSummary(BaseModel):
  main_idea: str
  theme: list[str]
  video_type: list[str]
  synopsis: list[str]
