from uuid import UUID
from sqlalchemy import insert, update, func
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
  
  async def create_serach(self, topic: Topic, scraper: str, kind: str, search_data: dict) -> TopicSearch:
    stmt = (
      insert(TopicSearch).
      values(topic_id=topic.id, scraper=scraper, kind=kind, search_data=search_data).
      returning(TopicSearch)
    )
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def update_search(self, serach_id: UUID, total_videos: int) -> TopicSearch:
    stmt = (
      update(TopicSearch).
      where(TopicSearch.id == serach_id).
      values(total_videos=total_videos, ran_at=func.now()).
      returning(TopicSearch)
    )
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def commit(self):
    await self._session.commit()
