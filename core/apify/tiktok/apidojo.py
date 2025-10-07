import logging
from typing import Any, cast, TypedDict
from apify_client import ApifyClientAsync
from core.apify.actor import BaseApifyActor
from core.apify.tiktok.clockwork import ActorRun


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
  duration: int
  cover: str


class SubtitleInformation(TypedDict, total=False):
  caption_format: str
  caption_length: int
  cla_subtitle_id: int
  complaint_id: int
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


class TikTokScrapperError(Exception):
  pass


class ApidojoTiktokScrapper(BaseApifyActor):
  
  def __init__(self, client: ApifyClientAsync):
    super().__init__(client)
    self.actor_client = client.actor('apidojo/tiktok-scraper')
    self._log = logging.getLogger("app.apify.tiktok.ad")
  
  async def scrape_videos(self) -> tuple[ActorRun, list[TikTokPost]]:
    try:
      run_input = {
        "dateRange": "THIS_MONTH",
        "includeSearchKeywords": True,
        "keywords": [
          "cat"
        ],
        "location": "US",
        "maxItems": 100,
        "sortType": "MOST_LIKED"
      }
      call_result = await self.actor_client.call(run_input=run_input, logger=self._log)
        
      if call_result is None:
        raise TikTokScrapperError("no call result")
      
      actor_run = cast(ActorRun, call_result)
      dataset = await self._get_dataset(call_result["defaultDatasetId"])
            
      return actor_run, dataset
    except Exception as e:
      raise TikTokScrapperError("run failed") from e
