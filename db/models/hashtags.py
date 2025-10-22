import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  Boolean,
  Enum,
  ForeignKey,
  String,
  Index,
  DateTime,
  func,
  text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base
from .enums import VideoSource


if TYPE_CHECKING:
  from .videos import Video


class Hashtag(Base):
  __tablename__ = "hashtags"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)
  source: Mapped[VideoSource] = mapped_column(
    Enum(VideoSource, name="hashtag_source", native_enum=True), nullable=False
  )
  is_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  video_hashtags: Mapped[list["VideoHashtag"]] = relationship(
    back_populates="hashtag",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos: Mapped[list["Video"]] = relationship(
    secondary="video_hashtags",
    back_populates="hashtags",
    viewonly=True,
  )

  __table_args__ = (
    Index("ix_hashtag_name_source", "name", "source", unique=True),
  )


class VideoHashtag(Base):
  __tablename__ = "video_hashtags"

  hashtag_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("hashtags.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  hashtag: Mapped["Hashtag"] = relationship(back_populates="video_hashtags")
  video: Mapped["Video"] = relationship(back_populates="video_hashtags")
