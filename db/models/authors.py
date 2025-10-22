import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  Boolean,
  Enum,
  Integer,
  String,
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
  is_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

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