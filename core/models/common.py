from typing import TypedDict

from pydantic import BaseModel


class PostDetails(TypedDict):
  url: str
  post_from: str
  title: str
  hashtags: list[str]
  

class VideoSummary(BaseModel):
  main_idea: str
  theme: list[str]
  video_type: list[str]
  synopsis: list[str]
