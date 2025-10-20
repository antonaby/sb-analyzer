from typing import TypedDict
from uuid import UUID


class VideoProcessingPipline(TypedDict):
  summarizing_job_id: UUID | None
  categorization_job_id: UUID | None
  delete_downloaded_files: bool
