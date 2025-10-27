from typing import Sequence
from uuid import UUID

from sqlalchemy import insert, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Challenge, ChallengeTranslation, ChallengeVideo, ChallengePattern
from db.repositories.common import BaseAsyncRepo, regconfig_for


class ChallengeRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def get_challenge_patterns(self, challenge_pattern_group_id: UUID) -> Sequence[ChallengePattern]:
    stmt = select(ChallengePattern).where(ChallengePattern.group_id == challenge_pattern_group_id)

    result = await self._session.execute(stmt)
    return result.scalars().all()

  async def get_challenge(self, challenge_id: UUID, with_translations: bool = True) -> Challenge | None:
    stmt = select(Challenge).where(Challenge.id == challenge_id)

    if with_translations:
      stmt = stmt.options(joinedload(Challenge.translations))

    result = await self._session.execute(stmt)
    return result.unique().scalar_one_or_none()

  async def create_challenge(self, topic_id: UUID, name: str) -> Challenge:
    stmt = (
      insert(Challenge).
      values(topic_id=topic_id, name=name).
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

  async def search_challenges(self, pattern_group: UUID, keywords: list[str]) -> Sequence[Challenge]:
    split = [" & ".join(k.split()) for k in keywords]
    query = " | ".join(split)

    ts_query = func.plainto_tsquery("english", query)

    stmt = (
      select(Challenge).
      where(
        (Challenge.group_id == pattern_group) & Challenge.name_tsv.op("@@")(ts_query)
      )
    )

    result = await self._session.execute(stmt)
    return result.scalars().all()


  async def commit(self):
    await self._session.commit()
