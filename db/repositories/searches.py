from uuid import UUID

from sqlalchemy import insert, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Search
from db.repositories.common import BaseAsyncRepo


class SearchRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_search(self, scraper: str, kind: str, search_data: dict) -> Search:
    stmt = (
      insert(Search).
      values(scraper=scraper, kind=kind, search_data=search_data).
      returning(Search)
    )
    result = await self._session.execute(stmt)

    return result.scalar_one()

  async def update_search(self, search_id: UUID, total_videos: int) -> Search:
    stmt = (
      update(Search).
      where(Search.id == search_id).
      values(total_videos=total_videos, ran_at=func.now()).
      returning(Search)
    )
    result = await self._session.execute(stmt)

    return result.scalar_one()

  async def commit(self):
    await self._session.commit()