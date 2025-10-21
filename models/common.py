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
