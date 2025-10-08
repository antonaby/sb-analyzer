import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import text

from core.utils import var_or_exception

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

async def get_session(async_session: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession]: 
  async with async_session() as session:              
    yield session                                     
