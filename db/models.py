import enum
import uuid
from datetime import datetime

from sqlalchemy import (
  Boolean,
  Enum,
  ForeignKey,
  Integer,
  BigInteger,
  Float,
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
  topic = "topic"


class AnnotationKind(enum.Enum):
  frame = "frame"
  frame_object = "frame_object"
  frame_action = "frame_action"
  frame_environment = "frame_environment"
  frame_summary = "frame_summary"
  frame_logo = "frame_logo"
  label = "label"
  synopsis = "synopsis"
  action = "action"
  transcription = "transcription"


# --- Models ------------------------------------------------------------
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
  
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  
  seraches: Mapped[list["TopicSearch"]] = relationship(
    back_populates="topic",
    cascade="all, delete-orphan",
    passive_deletes=True,
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
  
  def __repr__(self):
    return f"<Topic(id={self.id}, name={self.name!r})>"


class TopicSearch(Base):
  __tablename__ = "topic_searches"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
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
  
  topic: Mapped["Topic"] = relationship(back_populates="seraches")
  video_searches: Mapped[list["VideoSearch"]] = relationship(
    back_populates="search",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos: Mapped[list["Video"]] = relationship(
    secondary="video_searches",
    back_populates="seraches",
    viewonly=True,
  )
  

class Author(Base):
  __tablename__ = "authors"
  
  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
  source: Mapped[VideoSource] = mapped_column(
    Enum(VideoSource, name="video_source", native_enum=True), nullable=False
  )
  verified: Mapped[bool] = mapped_column(Boolean, nullable=True, server_default=text("false"))
  followers: Mapped[int] = mapped_column(Integer, nullable=True, server_default=text("0"))
  total_videos: Mapped[int] = mapped_column(Integer, nullable=True, server_default=text("0"))
  
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
  processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  processing_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
  
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
  video_searches: Mapped[list["VideoSearch"]] = relationship(
    back_populates="video",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  seraches: Mapped[list["TopicSearch"]] = relationship(
    secondary="video_searches",
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
  
  search: Mapped["TopicSearch"] = relationship(back_populates="video_searches")
  video: Mapped["Video"] = relationship(back_populates="video_searches")


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
