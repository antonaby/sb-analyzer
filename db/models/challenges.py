import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  ForeignKey,
  String,
  DateTime,
  func,
  text, Integer, Computed, Index
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .videos import Video


class ChallengePatternGroup(Base):
  __tablename__ = "challenge_pattern_group"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  patterns: Mapped[list["ChallengePattern"]] = relationship(
    back_populates="group",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  challenges: Mapped[list["Challenge"]] = relationship(
    back_populates="group",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )

class ChallengePattern(Base):
  __tablename__ = "challenge_patterns"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  group_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenge_pattern_group.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  value: Mapped[str] = mapped_column(String(1024), nullable=False)
  example: Mapped[str] = mapped_column(String(2048), nullable=False)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  group: Mapped["ChallengePatternGroup"] = relationship(back_populates="patterns")


class Challenge(Base):
  __tablename__ = "challenges"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  group_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenge_pattern_group.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)
  # Full-text search vector (auto-generated from value)
  name_tsv: Mapped[str] = mapped_column(
    TSVECTOR,
    Computed("to_tsvector('english', coalesce(name, ''))", persisted=True),
    nullable=False,
  )
  pattern_used: Mapped[str] = mapped_column(String(1024), nullable=False)
  translated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  group: Mapped["ChallengePatternGroup"] = relationship(back_populates="challenges")

  translations: Mapped[list["ChallengeTranslation"]] = relationship(
    back_populates="challenge",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  challenge_videos: Mapped[list["ChallengeVideo"]] = relationship(
    back_populates="challenge",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )
  videos: Mapped[list["Video"]] = relationship(
    secondary="challenge_videos",
    back_populates="challenges",
    viewonly=True,
  )

  __table_args__ = (
    Index("ix_challenge_name_tsv", "name_tsv", postgresql_using="gin"),
  )


class ChallengeTranslation(Base):
  __tablename__ = "challenge_translations"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  challenge_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenges.id", ondelete="CASCADE"),
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

  challenge: Mapped["Challenge"] = relationship(back_populates="translations")


class ChallengeVideo(Base):
  __tablename__ = "challenge_videos"

  challenge_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenges.id", ondelete="CASCADE"),
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

  challenge: Mapped["Challenge"] = relationship(back_populates="challenge_videos")
  video: Mapped["Video"] = relationship(back_populates="challenge_videos")
