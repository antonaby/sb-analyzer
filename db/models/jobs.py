import uuid
from datetime import datetime

from sqlalchemy import UUID, text, DateTime, func, Boolean, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.conf import Base


class ScraperJob(Base):
  __tablename__ = "scraper_jobs"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  scraper: Mapped[str] = mapped_column(String(128), nullable=False)
  meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )
