from pydantic import BaseModel, Field

from models.apidojo import DateRange, SortType


class ApidojoScrapperRun(BaseModel):
  keywords: list[str] = Field(min_length=1, description="At least one keyword")
  date_range: DateRange
  sort_type: SortType
  location: str
  max_items: int
