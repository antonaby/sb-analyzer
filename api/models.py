from pydantic import BaseModel, Field

from models.apidojo import DateRange, SortType


class CreateTopicRequest(BaseModel):
  name: str = Field(min_length=3, description="Topic name")


class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int


class ApidojoCollectUrls(BaseModel):
  urls: list[str] = Field(min_length=1, description="At least one url")
  max_items: int
