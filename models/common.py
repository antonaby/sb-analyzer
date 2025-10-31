from uuid import UUID

from pydantic import BaseModel


class BaseWorkflowSpec(BaseModel):
  delete_downloaded_files: bool
  pattern_group_id: UUID
  topic_group_id: UUID
  langs: list[str]
  append: bool