from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Topic


class TopicRepository:
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def create_topic(self, name: str) -> Topic:
    stmt = insert(Topic).values(name=name).returning(Topic)
    
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def commit(self):
    await self._session.commit()
