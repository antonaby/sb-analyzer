import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, text, DateTime, func, Enum, ForeignKey, BigInteger, Integer, Text, Computed, Boolean
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import Index

from db.conf import Base
from .enums import VideoSource, MetaSource, AnnotationKind, VideoProcessingKind


if TYPE_CHECKING:
  from .topics import Topic, VideoTopic
  from .authors import Author
  from .hashtags import Hashtag, VideoHashtag
  from .searches import Search, VideoSearch


class Video(Base):
  __tablename__ = "videos"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
  source: Mapped[VideoSource] = mapped_column(
    Enum(VideoSource, name="video_source", native_enum=True), nullable=False
  )
  author_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("authors.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )

  uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
  likes: Mapped[int] = mapped_column(BigInteger, nullable=True, server_default=text("0"))
  views: Mapped[int] = mapped_column(BigInteger, nullable=True, server_default=text("0"))
  comments: Mapped[int] = mapped_column(Integer, nullable=True, server_default=text("0"))

  revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
  extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  author: Mapped["Author"] = relationship(back_populates="videos")

  processing: Mapped[list["VideoProcessing"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  annotations: Mapped[list["VideoAnnotation"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  video_meta: Mapped[list["VideoMeta"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  scraped_data: Mapped[list["ScrapedData"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
    order_by="ScrapedData.created_at.desc()",
  )
  video_searches: Mapped[list["VideoSearch"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  searches: Mapped[list["Search"]] = relationship(
    secondary="video_searches",
    back_populates="videos",
    viewonly=True,
  )
  video_hashtags: Mapped[list["VideoHashtag"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  hashtags: Mapped[list["Hashtag"]] = relationship(
    secondary="video_hashtags",
    back_populates="videos",
    viewonly=True,
  )
  video_topics: Mapped[list["VideoTopic"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  topics: Mapped[list["Topic"]] = relationship(
    secondary="video_topics",
    back_populates="videos",
    viewonly=True,
  )


class VideoMeta(Base):
  __tablename__ = "video_meta"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  source: Mapped[MetaSource] = mapped_column(
    Enum(MetaSource, name="meta_source", native_enum=True),
    nullable=False,
  )
  revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
  value: Mapped[str] = mapped_column(Text, nullable=False)

  # Full-text search vector (auto-generated from value)
  value_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(value, ''))", persisted=True),
    nullable=False,
  )

  # Optional structured metadata (frame numbers, time ranges, etc.)
  meta: Mapped[dict | None] = mapped_column(JSONB, default=None)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  video: Mapped["Video"] = relationship(back_populates="video_meta")

  __table_args__ = (
    Index("ix_video_meta_value_tsv", "value_tsv", postgresql_using="gin"),
  )


class ScrapedData(Base):
  __tablename__ = "scraped_data"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  data: Mapped[dict | None] = mapped_column(JSONB, default=None)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(), nullable=False
  )

  video: Mapped["Video"] = relationship(back_populates="scraped_data")


class VideoAnnotation(Base):
  __tablename__ = "video_annotations"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  kind: Mapped[AnnotationKind] = mapped_column(
    Enum(AnnotationKind, name="annotation_kind", native_enum=True),
    nullable=False,
  )
  revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
  value: Mapped[str] = mapped_column(Text, nullable=False)

  # Full-text search vector (auto-generated from value)
  value_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(value, ''))", persisted=True),
    nullable=False,
  )

  # Optional structured metadata (frame numbers, time ranges, etc.)
  meta: Mapped[dict | None] = mapped_column(JSONB, default=None)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  video: Mapped["Video"] = relationship(back_populates="annotations")

  __table_args__ = (
    Index("ix_video_annotations_value_tsv", "value_tsv", postgresql_using="gin"),
  )


class VideoProcessing(Base):
  __tablename__ = "video_processing"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  source: Mapped[VideoProcessingKind] = mapped_column(
    Enum(VideoProcessingKind, name="video_processing_kind", native_enum=True), nullable=False
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )

  job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
  started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
  finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
  processing_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
  is_canceled: Mapped[bool | None] = mapped_column(Boolean, nullable=False, server_default=text("false"))

  video: Mapped["Video"] = relationship(back_populates="processing")
