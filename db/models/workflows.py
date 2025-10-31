import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, text, ForeignKey, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base


if TYPE_CHECKING:
  from .topics import TopicGroup
  from .challenges import ChallengePatternGroup
  from .videos import Video


class Workflow(Base):
  __tablename__ = "workflows"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  topic_group_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topic_groups.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  pattern_group_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("challenge_pattern_group.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  topic_group: Mapped["TopicGroup"] = relationship(back_populates="workflows")
  pattern_group: Mapped["ChallengePatternGroup"] = relationship(back_populates="workflows")
  processing: Mapped[list["VideoProcessing"]] = relationship(
    back_populates="workflow",
    cascade="all, delete-orphan",
    passive_deletes=True,
  )


class VideoProcessing(Base):
  __tablename__ = "video_processing_data"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  workflow_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("workflows.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  video_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("videos.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  processing_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
  categorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  categorization_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
  challenges_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  challenges_creating_error: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), onupdate=func.now(), nullable=False
  )

  video: Mapped["Video"] = relationship(back_populates="processing")
  workflow: Mapped["Workflow"] = relationship(back_populates="processing")
