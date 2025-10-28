from datetime import datetime
from typing import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, func, select, delete, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, aliased, selectinload, with_loader_criteria

from db.models import Challenge, ChallengeTranslation, ChallengeVideo, ChallengePattern, Video, ChallengeTopic, Topic
from db.repositories.common import BaseAsyncRepo, regconfig_for


class TranslationOnlyValue(BaseModel):
  lang: str
  value: str


class ChallengeWithTopic(BaseModel):
  id: UUID
  name: str
  created_at: datetime
  difficulty: float
  topic_id: UUID
  topic_name: str
  translations: list[TranslationOnlyValue]


class ChallengeRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def get_challenge_patterns(self, challenge_pattern_group_id: UUID) -> Sequence[ChallengePattern]:
    stmt = select(ChallengePattern).where(ChallengePattern.group_id == challenge_pattern_group_id)

    result = await self._session.execute(stmt)
    return result.scalars().all()

  async def get_challenge(self, challenge_id: UUID, with_translations: bool = False) -> Challenge | None:
    stmt = select(Challenge).where(Challenge.id == challenge_id)

    if with_translations:
      stmt = stmt.options(joinedload(Challenge.translations))

    result = await self._session.execute(stmt)
    return result.unique().scalar_one_or_none()

  async def create_challenge(self, group_id: UUID, name: str, pattern_used: str) -> Challenge:
    stmt = (
      insert(Challenge).
      values(group_id=group_id, name=name, pattern_used=pattern_used).
      returning(Challenge)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def create_translation(self, challenge_id: UUID, lang: str, value: str) -> ChallengeTranslation:
    stmt = (
      insert(ChallengeTranslation).
      values(
        challenge_id=challenge_id,
        lang=lang,
        value=value,
        value_tsv=func.to_tsvector(regconfig_for(lang), value)
      ).
      returning(ChallengeTranslation)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def delete_old_translations(self, challenge_id: UUID):
    stmt = delete(ChallengeTranslation).where(ChallengeTranslation.challenge_id == challenge_id)
    await self._session.execute(stmt)

  async def delete_old_topics(self, challenge_id: UUID):
    stmt = delete(ChallengeTopic).where(ChallengeTopic.challenge_id == challenge_id)
    await self._session.execute(stmt)

  async def unassign_videos(self, challenge_group_id: UUID, video_id: UUID):
    cv = aliased(ChallengeVideo)
    c = aliased(Challenge)
    v = aliased(Video)

    stmt = (
      delete(cv).
      where(cv.challenge_id == c.id).
      where(cv.video_id == v.id).
      where(
        (c.group_id == challenge_group_id) & (v.id == video_id)
      )
    )
    await self._session.execute(stmt)

  async def add_video(self, challenge_id: UUID, video_id: UUID) -> ChallengeVideo:
    stmt = (
      pg_insert(ChallengeVideo)
      .values(challenge_id=challenge_id, video_id=video_id)
      .on_conflict_do_update(  # type: ignore
        index_elements=[ChallengeVideo.challenge_id, ChallengeVideo.video_id],
        set_={
          "created_at": func.now()
        }
      )
      .returning(ChallengeVideo)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def add_topic(self, challenge_id: UUID, topic_id: UUID) -> ChallengeTopic:
    stmt = (
      pg_insert(ChallengeTopic).
      values(challenge_id=challenge_id, topic_id=topic_id).
      on_conflict_do_update(  # type: ignore
        index_elements=[ChallengeTopic.topic_id, ChallengeTopic.challenge_id],
        set_={
          "created_at": func.now()
        }
      ).
      returning(ChallengeTopic)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def set_challenge_categorization(self, challenge_id: UUID, with_error: bool):
    stmt = update(Challenge).where(Challenge.id == challenge_id).values(categorized_at=func.now(), categorization_error=with_error)
    await self._session.execute(stmt)

  async def search_challenges(self, pattern_group: UUID, keywords: list[str]) -> Sequence[Challenge]:
    split = [" & ".join(k.split()) for k in keywords]
    query = " | ".join(split)

    ts_query = func.to_tsquery("english", query)

    stmt = (
      select(Challenge).
      where(
        (Challenge.group_id == pattern_group) & Challenge.name_tsv.op("@@")(ts_query)
      )
    )

    result = await self._session.execute(stmt)
    return result.scalars().all()

  async def get_challenges_by_topics(self,
                                     topic_ids: list[UUID],
                                     min_difficulty: float | None = None,
                                     max_difficulty: float | None = None,
                                     langs: list[str] | None = None,
                                     only_valid: bool = True) -> list[ChallengeWithTopic]:
    conditions = [
      Topic.id.in_(topic_ids)
    ]

    if only_valid:
      conditions.append(
        and_(
          Challenge.translated_at.isnot(None), Challenge.categorization_error.is_(False)
        )
      )

    if min_difficulty:
      conditions.append(
        Challenge.difficulty >= min_difficulty
      )

    if max_difficulty:
      conditions.append(
        Challenge.difficulty <= max_difficulty
      )

    stmt = (
      select(Challenge, Topic).
      join(ChallengeTopic, ChallengeTopic.challenge_id == Challenge.id).
      join(Topic, ChallengeTopic.topic_id == Topic.id).
      where(*conditions).
      order_by(Challenge.created_at.desc())
    )

    if langs:
      stmt = stmt.options(
        selectinload(Challenge.translations),
        with_loader_criteria(ChallengeTranslation, ChallengeTranslation.lang.in_(langs))
      )

    result = await self._session.execute(stmt)
    challenges: list[ChallengeWithTopic] = []
    for challenge, topic in result.all():
      translations: list[ChallengeTranslation] = challenge.translations if langs else []

      challenges.append(
        ChallengeWithTopic(
          id=challenge.id,
          name=challenge.name,
          created_at=challenge.created_at,
          difficulty=challenge.difficulty,
          topic_id=topic.id,
          topic_name=topic.name,
          translations=[TranslationOnlyValue(lang=t.lang, value=t.value) for t in translations]
        )
      )

    return challenges

  async def commit(self):
    await self._session.commit()
