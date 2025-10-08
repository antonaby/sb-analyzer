import logging
from typing import Any, TypedDict, cast

from apify_client import ApifyClientAsync

from core.apify.actor import BaseApifyActor
from core.models.apify import ActorRun


class AuthorMeta(TypedDict, total=False):
  id: str
  name: str
  profileUrl: str
  nickName: str
  verified: bool
  signature: str
  bioLink: str | None
  originalAvatarUrl: str
  avatar: str
  privateAccount: bool
  following: int
  friends: int
  fans: int
  heart: int
  video: int
  digg: int


class MusicMeta(TypedDict, total=False):
  musicName: str
  musicAuthor: str
  musicOriginal: bool
  musicAlbum: str
  playUrl: str
  coverMediumUrl: str
  originalCoverMediumUrl: str
  musicId: str


class SubtitleLink(TypedDict, total=False):
  language: str
  downloadLink: str
  tiktokLink: str
  source: str
  sourceUnabbreviated: str
  version: str


class VideoMeta(TypedDict, total=False):
  height: int
  width: int
  duration: int  # seconds
  coverUrl: str
  originalCoverUrl: str
  definition: str
  format: str
  subtitleLinks: list[SubtitleLink]
  downloadAddr: str


class Hashtag(TypedDict, total=False):
  name: str


class SearchHashtag(TypedDict, total=False):
  views: int
  name: str


class StickerStats(TypedDict, total=False):
  useCount: int


class EffectSticker(TypedDict, total=False):
  ID: str
  name: str
  stickerStats: StickerStats


# ---------- Root type of Dataset ----------
class TikTokPost(TypedDict, total=False):
  id: str
  text: str
  textLanguage: str
  createTime: int                 # Unix seconds
  createTimeISO: str              # ISO8601 string, e.g. "2025-10-01T02:18:35.000Z"
  isAd: bool
  authorMeta: AuthorMeta
  musicMeta: MusicMeta
  webVideoUrl: str
  mediaUrls: list[str]
  videoMeta: VideoMeta
  diggCount: int
  shareCount: int
  playCount: int
  collectCount: int
  commentCount: int
  mentions: list[str]
  detailedMentions: list[str]
  hashtags: list[Hashtag]
  effectStickers: list[str] | list[EffectSticker]
  isSlideshow: bool
  isPinned: bool
  isSponsored: bool
  input: str
  searchHashtag: SearchHashtag


class TikTokScrapperError(Exception):
  pass


class ClockworksTiktokScrapper(BaseApifyActor):
  
  def __init__(self, client: ApifyClientAsync):
    super().__init__(client)
    self.actor_client = client.actor('clockworks/tiktok-scraper')
    self._log = logging.getLogger("app.apify.tiktok.clockworks")
  
  async def scrape_hashtags(
    self, 
    hashtags: list[str], 
    max_results: int = 1000, 
    download: bool = True
  ) -> tuple[ActorRun, list[TikTokPost]]:
    try:
      run_input = {
        "excludePinnedPosts": True,
        "hashtags": hashtags,
        "proxyCountryCode": "None",
        "resultsPerPage": max_results,
        "scrapeRelatedVideos": False,
        "searchSection": "/video",
        "shouldDownloadAvatars": False,
        "shouldDownloadCovers": False,
        "shouldDownloadMusicCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadVideos": download
      }
      
      call_result = await self.actor_client.call(run_input=run_input, logger=self._log)
      
      if call_result is None:
        raise TikTokScrapperError("no call result")
      
      actor_run = cast(ActorRun, call_result)
      dataset = await self._get_dataset(call_result["defaultDatasetId"])
           
      return actor_run, dataset
    except Exception as e:
      raise TikTokScrapperError("run failed") from e
