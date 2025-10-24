import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  ForeignKey,
  String,
  DateTime,
  func,
  text, Integer
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .videos import Video


class ChallengeGroup(Base):
  __tablename__ = "challenge_groups"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  main_topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  additional_topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  last_challenges_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  last_batch: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  challenges: Mapped[list["Challenge"]] = relationship(
    back_populates="group",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )


class Challenge(Base):
  __tablename__ = "challenges"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  challenge_group_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenge_groups.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)
  batch: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  translated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

  group: Mapped["ChallengeGroup"] = relationship(back_populates="challenges")
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
