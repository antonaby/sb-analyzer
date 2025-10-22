import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
  ForeignKey,
  String,
  DateTime,
  func,
  text
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.conf import Base

if TYPE_CHECKING:
  from .topics import Topic


class Challenge(Base):
  __tablename__ = "challenges"

  id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v1mc()")
  )
  topic_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("topics.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
  )
  name: Mapped[str] = mapped_column(String(512), nullable=False)

  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(), nullable=False
  )
  translated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

  topic: Mapped["Topic"] = relationship(back_populates="challenges")
  translations: Mapped[list["ChallengeTranslation"]] = relationship(
    back_populates="challenge",
    cascade="all, delete-orphan",
    passive_deletes=True,
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