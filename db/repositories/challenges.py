from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Challenge
from db.repositories.common import BaseAsyncRepo


class ChallengeRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_challenge(self, topic_id: UUID, name: str) -> Challenge:
    stmt = (
      insert(Challenge).
      values(topic_id=topic_id, name=name).
      returning(Challenge)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def commit(self):
    await self._session.commit()
