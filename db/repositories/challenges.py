from typing import Final
from uuid import UUID

from sqlalchemy import insert, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Challenge, ChallengeTranslation, ChallengeVideo
from db.repositories.common import BaseAsyncRepo


REGCONFIG_BY_LANG: Final[dict[str, str]] = {
  "en": "english",
  "fr": "french",
  "de": "german",
  "es": "spanish",
  "it": "italian",
  "pt": "portuguese",
  "ru": "russian",
  "nl": "dutch",
  "sv": "swedish",
  "no": "norwegian",
  "da": "danish",
  "fi": "finnish",
  "ro": "romanian",
  "hu": "hungarian",
  "tr": "turkish",
  "cs": "czech",
  "ar": "arabic",
  "zh": "simple",
  "ja": "simple",
}


def regconfig_for(lang: str) -> str:
  return REGCONFIG_BY_LANG.get(lang.lower(), "english")


class ChallengeRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

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

  async def commit(self):
    await self._session.commit()
