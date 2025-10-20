from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Author
from db.repositories.common import BaseAsyncRepo


class AuthorRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def get_author_by_id(self, author_id: UUID) -> Author | None:
    stmt = select(Author).where(Author.id == author_id)

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def set_author_reviewed_status(self, author_id: UUID, is_reviewed: bool) -> Author | None:
    stmt = (
      update(Author).
      where(Author.id == author_id).
      values(is_reviewed=is_reviewed).
      returning(Author)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def commit(self):
    await self._session.commit()
