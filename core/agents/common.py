from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from db.repositories.topics import TopicRepository


class TopicDetails(BaseModel):
  id: UUID
  name: str


class TopicLoader:
  
  def __init__(self, async_session: async_sessionmaker[AsyncSession]) -> None:
    self._db = async_session
    
  async def search_topics(self, search_keywords: list[str]) -> list[TopicDetails]:
    async with self._db() as session:
      topic_repo = TopicRepository(session)
          
      found_topics = await topic_repo.search_topics(search_keywords)
      return [
        TopicDetails(id=t.id, name=t.name) 
        for t in found_topics
      ]
