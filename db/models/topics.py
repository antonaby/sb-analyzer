import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, text, Computed, DateTime, func, Index, ForeignKey, Float
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .videos import Video
  from .challenges import Challenge


class Topic(Base):
  __tablename__ = "topics"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)
  # Full-text search vector (auto-generated from name)
  name_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(name, ''))", persisted=True),
    nullable=False,
  )
  last_challenges_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  video_topics: Mapped[list["VideoTopic"]] = relationship(
    back_populates="topic",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos: Mapped[list["Video"]] = relationship(
    secondary="video_topics",
    back_populates="topics",
    viewonly=True,
  )
  challenges: Mapped[list["Challenge"]] = relationship(
    back_populates="topic",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )

  __table_args__ = (
    Index("ix_topic_name_tsv", "name_tsv", postgresql_using="gin"),
  )

  def __repr__(self):
    return f"<Topic(id={self.id}, name={self.name!r})>"


class VideoTopic(Base):
  __tablename__ = "video_topics"

  topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    primary_key=True,
  )
  confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  topic: Mapped["Topic"] = relationship(back_populates="video_topics")
  video: Mapped["Video"] = relationship(back_populates="video_topics")
