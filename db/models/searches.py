import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  Boolean,
  ForeignKey,
  Integer,
  String,
  DateTime,
  func,
  text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .videos import Video


class Search(Base):
  __tablename__ = "topic_searches"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  scraper: Mapped[str] = mapped_column(String(128), nullable=False)
  kind: Mapped[str] = mapped_column(String(128), nullable=False)
  search_data: Mapped[dict] = mapped_column(JSONB, default={}, nullable=False)
  total_videos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  ran_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  video_searches: Mapped[list["VideoSearch"]] = relationship(
    back_populates="search",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos: Mapped[list["Video"]] = relationship(
    secondary="video_searches",
    back_populates="searches",
    viewonly=True,
  )


class VideoSearch(Base):
  __tablename__ = "video_searches"

  search_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topic_searches.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  search: Mapped["Search"] = relationship(back_populates="video_searches")
  video: Mapped["Video"] = relationship(back_populates="video_searches")
