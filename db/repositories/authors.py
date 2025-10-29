from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select, update, func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Author, VideoSource
from db.repositories.common import BaseAsyncRepo


class AuthorRepository(BaseAsyncRepo):

  def __init__(self, session: AsyncSession):
    self._session = session

  async def upsert_author(
      self,
      url: str, source: VideoSource,
      verified: bool | None, followers: int | None, total_videos: int | None) -> tuple[Author, bool]:

    update_values: dict[str, Any] = {"updated_at": func.now()}

    if verified is not None:
      update_values["verified"] = verified
    if followers is not None:
      update_values["followers"] = followers
    if total_videos is not None:
      update_values["total_videos"] = total_videos

    stmt = (
      pg_insert(Author)
      .values(url=url, source=source, verified=verified, followers=followers, total_videos=total_videos)
      .on_conflict_do_update(  # type: ignore
        index_elements=[Author.url],
        set_=update_values
      )
      .returning(Author, literal_column("xmax"))
    )

    result = await self._session.execute(stmt)
    row, xmax = result.first()  # type: ignore
    author: Author = row
    is_new = xmax == 0

    return author, is_new

  async def get_author_by_id(self, author_id: UUID) -> Author | None:
    stmt = select(Author).where(Author.id == author_id)

    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def get_authors(self) -> Sequence[Author]:
    stmt = select(Author)

    result = await self._session.execute(stmt)
    return result.scalars().all()

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
