import enum
import uuid
from datetime import datetime

from sqlalchemy import (
  Enum,
  ForeignKey,
  String,
  Text,
  Index,
  Computed,
  DateTime,
  func,
  text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

from db.conf import Base


# --- Enums -------------------------------------------------------------

class VideoSource(enum.Enum):
  tiktok = "tiktok"
  youtube_shorts = "youtube_shorts"
  instagram_reels = "instagram_reels"
  other = "other"


class MetaSource(enum.Enum):
  title = "title"
  description = "description"
  hashtag = "hashtag"
  frame_content_type = "frame_content_type"
  frame_style = "frame_style"
  frame_quality = "frame_quality"
  summary = "summary"
  summary_video_type = "summary_video_type"


class AnnotationKind(enum.Enum):
  frame = "frame"
  frame_object = "frame_object"
  frame_action = "frame_action"
  frame_environment = "frame_environment"
  frame_summary = "frame_summary"
  frame_logo = "frame_logo"
  summary = "summary"
  summary_synopsis = "summary_synopsis"
  transcription = "transcription"


# --- Models ------------------------------------------------------------
class Author(Base):
  __tablename__ = "authors"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
  source: Mapped[VideoSource] = mapped_column(
    Enum(VideoSource, name="video_source", native_enum=True), nullable=False
  )
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )
  
  videos: Mapped[list["Video"]] = relationship(
    back_populates="author",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  

class Video(Base):
  """
  One row per video.
  """
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
  extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
  
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )
  processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  
  author: Mapped["Author"] = relationship(back_populates="videos")

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
  
  scraped_data: Mapped["ScrapedData"] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
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
  value: Mapped[str] = mapped_column(Text, nullable=False)

  # Full-text search vector (auto-generated from value)
  value_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(value, ''))", persisted=True),
    nullable=False,
  )
  
  # Optional structured metadata (frame numbers, time ranges, etc.)
  meta: Mapped[dict | None] = mapped_column(JSONB, default=None)
  
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
  
  video: Mapped["Video"] = relationship(back_populates="scraped_data")


class VideoAnnotation(Base):
  """
  Many rows per video. Each row stores one piece of text the LLM produced,
  plus optional JSON metadata (e.g., frame number, time range).
  Includes PostgreSQL full-text search with tsvector.
  """
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
  value: Mapped[str] = mapped_column(Text, nullable=False)

  # Full-text search vector (auto-generated from value)
  value_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(value, ''))", persisted=True),
    nullable=False,
  )

  # Optional structured metadata (frame numbers, time ranges, etc.)
  meta: Mapped[dict | None] = mapped_column(JSONB, default=None)

  video: Mapped["Video"] = relationship(back_populates="annotations")

  __table_args__ = (
    Index("ix_video_annotations_value_tsv", "value_tsv", postgresql_using="gin"),
  )
