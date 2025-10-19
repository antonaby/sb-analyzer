
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from utils.common import var_or_exception

DATABASE_URL_VAR = 'DATABASE_URL'


class Base(DeclarativeBase):
  pass


# TODO: add pool size and other params
def create_db_engine() -> AsyncEngine:
  return create_async_engine(
    var_or_exception(DATABASE_URL_VAR), echo=True
  )


def get_async_session(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
  return async_sessionmaker(
    engine, expire_on_commit=False
  )


async def test_db_conn(session: AsyncSession) -> int | None:
  result = await session.execute(text("SELECT 1"))
  return result.scalar()
