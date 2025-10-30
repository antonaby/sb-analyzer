from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from apify.actor import ActorRun
from apify.tiktok.apidojo import DateRange, SortType

ApidojoFunc = Literal[
  "search",
  "collect_videos_by_urls"
]


class ApidojoSearch(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


class ApidojoCollectUrls(BaseModel):
  urls: list[str] = Field(min_length=1, description="At least one url")
  max_items: int


class ApidojoActorSpec(BaseModel):
  func: ApidojoFunc
  args: ApidojoSearch | ApidojoCollectUrls


class ApidojoPostProcessorSpec(BaseModel):
  search_id: UUID
  actor_run: ActorRun


class ApidojoWorkflow(BaseModel):
  actor_spec: ApidojoActorSpec
  delete_downloaded_files: bool
  topic_group_id: UUID
  pattern_group_id: UUID
  langs: list[str]
  append: bool
