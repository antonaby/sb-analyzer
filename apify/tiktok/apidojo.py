import logging
from typing import cast, Literal, TypedDict
from apify_client import ApifyClientAsync
from apify.actor import BaseApifyActor, ActorRun


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
  hashtags: list[str] | None
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


class ApidojoTikTokScrapperError(Exception):
  pass


class ApidojoTiktokScrapper(BaseApifyActor):
  
  def __init__(self, client: ApifyClientAsync):
    super().__init__(client)
    self.actor_client = client.actor('apidojo/tiktok-scraper')
    self._log = logging.getLogger("app.apify.tiktok.apidojo")
  
  async def search(self,
                   keywords: list[str],
                   date_range: DateRange,
                   sort_type: SortType,
                   location: str = "US",
                   max_items: int = 1000) -> ActorRun:
    run_input = {
      "dateRange": date_range,
      "includeSearchKeywords": True,
      "keywords": keywords,
      "location": location,
      "maxItems": max_items,
      "sortType": sort_type
    }
    
    return await self._run(run_input)
  
  async def collect_videos_by_urls(self, urls: list[str], max_items: int = 1000) -> ActorRun:
    run_input = {
      "startUrls": urls,
      "maxItems": max_items
    }
    
    return await self._run(run_input)
    
  async def _run(self, run_input: dict) -> ActorRun:
    try:
      call_result = await self.actor_client.call(run_input=run_input, logger=self._log)
        
      if call_result is None:
        raise ApidojoTikTokScrapperError("no call result")
      
      actor_run = cast(ActorRun, call_result)
            
      return actor_run
    except Exception as e:
      raise ApidojoTikTokScrapperError("run failed") from e
