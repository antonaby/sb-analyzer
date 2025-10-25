import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, text, DateTime, func, ForeignKey, Float
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .videos import Video


class Topic(Base):
  __tablename__ = "topics"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)

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
  translations: Mapped[list["TopicTranslation"]] = relationship(
    back_populates="topic",
    cascade="all, delete-orphan",
    passive_deletes=True,
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


class TopicTranslation(Base):
  __tablename__ = "topic_translations"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  lang: Mapped[str] = mapped_column(String(2), nullable=False)
  value: Mapped[str] = mapped_column(String(512), nullable=False)
  value_tsv: Mapped[str] = mapped_column(TSVECTOR, nullable=False)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  topic: Mapped["Topic"] = relationship(back_populates="translations")
