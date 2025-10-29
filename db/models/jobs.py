import uuid
from datetime import datetime

from sqlalchemy import UUID, text, DateTime, func, Boolean, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.conf import Base


class Job(Base):
  __tablename__ = "jobs"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  name: Mapped[str] = mapped_column(String(128), nullable=False)
  meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

  celery_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
  started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  processing_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  def __repr__(self):
    return f"<Job(id={self.id}, name={self.name!r}, meta={self.meta!r})>"


class ScraperJob(Base):
  __tablename__ = "scraper_jobs"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  scraper: Mapped[str] = mapped_column(String(128), nullable=False)
  meta: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
  last_job_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("jobs.id", ondelete="SET NULL"),
    nullable=True
  )

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )
