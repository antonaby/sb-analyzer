import logging
import re
from typing import Any, TypedDict, cast

from apify_client import ApifyClientAsync


class Meta(TypedDict):
  origin: str

class PricingPerEvent(TypedDict):
  actorChargeEvents: dict[str, Any]

class PricingInfo(TypedDict):
  apifyMarginPercentage: int
  createdAt: str
  startedAt: str
  notifiedAboutFutureChangeAt: str
  notifiedAboutChangeAt: str
  reasonForChange: str
  pricingModel: str
  pricingPerEvent: PricingPerEvent
  minimalMaxTotalChargeUsd: float

class Stats(TypedDict):
  inputBodyLen: int
  migrationCount: int
  restartCount: int
  resurrectCount: int
  memAvgBytes: float
  memMaxBytes: int
  memCurrentBytes: int
  cpuAvgUsage: float
  cpuMaxUsage: float
  cpuCurrentUsage: int
  netRxBytes: int
  netTxBytes: int
  durationMillis: int
  runTimeSecs: float
  metamorph: int
  computeUnits: float

class Options(TypedDict):
  build: str
  timeoutSecs: int
  memoryMbytes: int
  diskMbytes: int

# ---------- Root type of Actor ----------
class ActorRun(TypedDict):
  id: str
  actId: str
  userId: str
  actorTaskId: str
  startedAt: str
  finishedAt: str
  status: str
  statusMessage: str
  isStatusMessageTerminal: bool
  meta: Meta
  pricingInfo: PricingInfo
  stats: Stats
  chargedEventCounts: dict[str, Any]
  options: Options
  buildId: str
  exitCode: int
  defaultKeyValueStoreId: str
  defaultDatasetId: str
  defaultRequestQueueId: str
  buildNumber: str
  containerUrl: str
  isContainerServerReady: bool
  gitBranchName: str
  usageTotalUsd: float

class AuthorMeta(TypedDict):
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

class MusicMeta(TypedDict):
  musicName: str
  musicAuthor: str
  musicOriginal: bool
  playUrl: str
  coverMediumUrl: str
  originalCoverMediumUrl: str
  musicId: str

class SubtitleLink(TypedDict):
  language: str
  downloadLink: str
  tiktokLink: str
  source: str
  sourceUnabbreviated: str
  version: str

class VideoMeta(TypedDict):
  height: int
  width: int
  duration: int  # seconds
  coverUrl: str
  originalCoverUrl: str
  definition: str
  format: str
  subtitleLinks: list[SubtitleLink]
  downloadAddr: str

class Hashtag(TypedDict):
  name: str

class SearchHashtag(TypedDict):
  views: int
  name: str

# ---------- Root type of Dataset ----------
class TikTokPost(TypedDict):
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
  effectStickers: list[str]
  isSlideshow: bool
  isPinned: bool
  isSponsored: bool
  input: str
  searchHashtag: SearchHashtag

class TikTokScrapperError(Exception):
  pass

class ClockworksTiktokScrapper:
  
  def __init__(self, client: ApifyClientAsync):
    self.client = client
    self.actor_client = client.actor('clockworks/tiktok-scraper')
    self.log = logging.getLogger("app.apify.tiktok")
  
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
      
      call_result = await self.actor_client.call(run_input=run_input, logger=self.log)
      
      if call_result is None:
        raise TikTokScrapperError("no call result")
      
      actor_run = cast(ActorRun, call_result)
      dataset = await self._get_dataset(call_result["defaultDatasetId"])
           
      return actor_run, dataset
    except Exception as e:
      raise TikTokScrapperError("run failed") from e
    
  async def _get_dataset(self, dataset_id: str) -> list[TikTokPost]:
    dataset_client = self.client.dataset(dataset_id)
    items = await dataset_client.list_items()
    
    return items.items

  async def download_video(self, post: TikTokPost) -> bytes:
    url = post.get("videoMeta", {}).get("downloadAddr")
    if not url:
      raise TikTokScrapperError("no valid video url")
    
    match = re.search(r"/key-value-stores/([^/]+)/records/(.+)$", url)
    if match:
      store_id = match.group(1)
      filename = match.group(2)
      try:
        return await self._download_video(store_id, filename)
      except Exception as e:
        raise TikTokScrapperError("donwload filed") from e

    raise TikTokScrapperError("no valid video url")

  async def _download_video(self, kv_store_id: str, record: str) -> bytes:
    kv_store = self.client.key_value_store(kv_store_id)
    entry = await kv_store.get_record(record)
    
    if entry is None:
      raise TikTokScrapperError(f"cannot get record: {kv_store_id}/{record}")
    
    return entry["value"]
  