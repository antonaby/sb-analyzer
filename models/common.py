from typing import TypedDict


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


class VideoData(TypedDict):
  video_id: str
  source: str
  title: str
  description: str
  uploaded_at_iso: str
  likes: int
  views: int
  comments: int
  hashtags: list[str]
  topics: list[str]
  label: str
  synopsis: str
  actions: list[str]
  transcription: list[str]
