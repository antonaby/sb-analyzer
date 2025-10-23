from datetime import datetime
from typing import Any, TypedDict

from apify_client import ApifyClientAsync
from abc import ABC


class Meta(TypedDict, total=False):
  origin: str


class PricingPerEvent(TypedDict, total=False):
  actorChargeEvents: dict[str, Any]


class PricingInfo(TypedDict, total=False):
  apifyMarginPercentage: float
  createdAt: datetime
  startedAt: datetime
  notifiedAboutFutureChangeAt: datetime
  notifiedAboutChangeAt: datetime
  reasonForChange: str
  pricingModel: str
  pricingPerEvent: PricingPerEvent
  minimalMaxTotalChargeUsd: float


class Stats(TypedDict, total=False):
  inputBodyLen: int
  migrationCount: int
  restartCount: int
  resurrectCount: int
  memAvgBytes: float
  memMaxBytes: int
  memCurrentBytes: int
  cpuAvgUsage: float
  cpuMaxUsage: float
  cpuCurrentUsage: float
  netRxBytes: int
  netTxBytes: int
  durationMillis: int
  runTimeSecs: float
  metamorph: int
  computeUnits: float


class Options(TypedDict, total=False):
  build: str
  timeoutSecs: int
  memoryMbytes: int
  diskMbytes: int


# ---------- Root type of Actor ----------
class ActorRun(TypedDict, total=False):
  id: str
  actId: str
  userId: str
  actorTaskId: str
  startedAt: datetime
  finishedAt: datetime
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


class BaseApifyActor(ABC):
  
  def __init__(self, client: ApifyClientAsync):
    self.client = client
