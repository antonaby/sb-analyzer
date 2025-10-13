from uuid import UUID
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Topic, TopicSearch
from db.repositories.common import BaseAsyncRepo


class TopicRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def create_topic(self, name: str) -> Topic:
    stmt = insert(Topic).values(name=name).returning(Topic)
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def get_topic(self, topic_id: UUID) -> Topic | None:
    return await self._session.get(Topic, topic_id)
  
  async def create_serach(self, topic: Topic, kind: str, search_data: dict) -> TopicSearch:
    stmt = (
      insert(TopicSearch).
      values(topic_id=topic.id, kind=kind, search_data=search_data).
      returning(TopicSearch)
    )
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def commit(self):
    await self._session.commit()
