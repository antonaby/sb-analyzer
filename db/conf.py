import os

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
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

async def test_connection(engine: AsyncEngine):
  async with engine.connect() as conn:  
    result = await conn.execute(text("SELECT 1")) # type: ignore
    print(result.scalar())

def create_session_maker(engine: AsyncEngine):
  return sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False # type: ignore
  )

async def get_session(async_session): 
  async with async_session() as session:              
    yield session                                     
