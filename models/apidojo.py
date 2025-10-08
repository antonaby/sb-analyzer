from typing import Literal, TypedDict


class Channel(TypedDict, total=False):
  name: str
  username: str
  id: str
  url: str
  avatar: str
  verified: bool
  followers: int
  following: int


class Video(TypedDict, total=False):
  width: int
  height: int
  ratio: str
  duration: float
  url: str
  cover: str
  thumbnail: str


class Song(TypedDict, total=False):
  id: str
  title: str
  artist: str
  duration: float
  cover: str


class SubtitleInformation(TypedDict, total=False):
  caption_format: str
  caption_length: int
  cla_subtitle_id: float
  complaint_id: float
  expire: int
  is_auto_generated: bool
  is_original_caption: bool
  lang: str
  language_code: str
  language_id: int
  source_tag: str
  sub_id: int
  sub_version: str
  subtitle_type: int
  translation_type: int
  translator_id: int
  url: str
  url_list: list[str]
  variant: str


class TikTokPost(TypedDict, total=False):
  id: str
  title: str
  textLanguage: str
  views: int
  likes: int
  comments: int
  shares: int
  bookmarks: int
  hashtags: list[str]
  channel: Channel
  uploadedAt: int
  uploadedAtFormatted: str
  video: Video
  song: Song
  subtitleInformation: list[SubtitleInformation]
  postPage: str
  keyword: str


SortType = Literal[
  "RELEVANCE",
  "MOST_LIKED",
  "DATE_POSTED",
]


DateRange = Literal[
  "DEFAULT",
  "ALL_TIME",
  "YESTERDAY",
  "THIS_WEEK",
  "THIS_MONTH",
  "LAST_THREE_MONTHS",
  "LAST_SIX_MONTHS",
]
