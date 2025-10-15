from typing import Sequence, TypedDict
from uuid import UUID
from sqlalchemy import desc, insert, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Topic, TopicSearch
from db.repositories.common import BaseAsyncRepo
from models.common import TopicData


class TopicRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def create_topic(self, name: str) -> Topic:
    stmt = insert(Topic).values(name=name).returning(Topic)
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def get_topic(self, topic_id: UUID) -> Topic | None:
    return await self._session.get(Topic, topic_id)
  
  async def fetch_all_topics(self) -> Sequence[Topic]:
    stmt = select(Topic).order_by(desc(Topic.created_at))
    result = await self._session.execute(stmt)
    
    return result.scalars().all()
    
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
    

class TopicLoader:
  
  def __init__(self, topic_repo: TopicRepository):
    self._topic_repo = topic_repo
  
  async def load_topics(self) -> list[TopicData]:
    topics = await self._topic_repo.fetch_all_topics()
    
    return [
      {
        "id": str(t.id),
        "name": t.name
      } 
      for t in topics
    ]
