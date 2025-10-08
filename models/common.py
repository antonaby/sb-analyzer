from typing import TypedDict

from pydantic import BaseModel


class PostDetails(TypedDict):
  url: str
  download_url: str
  post_from: str
  title: str
  author: str
  hashtags: list[str]
  meta: dict
  

class VideoSummary(BaseModel):
  main_idea: str
  theme: list[str]
  video_type: list[str]
  synopsis: list[str]
