import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, text, DateTime, func, ForeignKey, Float, CheckConstraint
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
  video_additional_topics: Mapped[list["VideoAdditionalTopic"]] = relationship(
    back_populates="topic",
    primaryjoin="Topic.id == foreign(VideoAdditionalTopic.additional_topic_id)",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos_as_additional: Mapped[list["Video"]] = relationship(
    secondary="video_additional_topics",
    primaryjoin="Topic.id == foreign(VideoAdditionalTopic.additional_topic_id)",
    secondaryjoin="Video.id == foreign(VideoAdditionalTopic.video_id)",
    back_populates="additional_topics",
    viewonly=True,
  )
  challenges: Mapped[list["Challenge"]] = relationship(
    back_populates="topic",
    cascade="all, delete-orphan",
    passive_deletes=True,
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


class VideoAdditionalTopic(Base):
  __tablename__ = "video_additional_topics"

  video_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, primary_key=True
  )
  main_topic_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, primary_key=True
  )
  additional_topic_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, primary_key=True
  )
  confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  __table_args__ = (
    CheckConstraint("main_topic_id <> additional_topic_id", name="chk_main_not_equal_additional"),
  )

  video: Mapped["Video"] = relationship(back_populates="video_additional_topics")
  topic: Mapped["Topic"] = relationship(
    foreign_keys=[additional_topic_id],
    back_populates="video_additional_topics"
  )


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
