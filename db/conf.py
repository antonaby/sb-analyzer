import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text

from core.utils import var_or_exception

DATABASE_URL_VAR = 'DATABASE_URL'

# TODO: add pool size and other params
engine = create_async_engine(
  var_or_exception(DATABASE_URL_VAR), echo=True
)


class Base(DeclarativeBase):
  pass


async_session = sessionmaker(
  engine, class_=AsyncSession, expire_on_commit=False # type: ignore
)


async def get_session() -> AsyncSession: # type: ignore
  async with async_session() as session: # type: ignore
    yield session                        # type: ignore


async def test_connection():
  async with engine.connect() as conn:  
    result = await conn.execute(text("SELECT 1")) # type: ignore
    print(result.scalar())
