from typing import Sequence, TypedDict
from uuid import UUID
from sqlalchemy import desc, insert, select, text, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Topic, Search, Video, VideoTopic
from db.repositories.common import BaseAsyncRepo
from sqlalchemy.dialects.postgresql import insert as pg_insert


TOPIC_LOCK_KEY: int = 1


class TopicWithCount(TypedDict):
  id: UUID
  name: str
  total_videos: int


class TopicRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session
  
  async def topic_lock(self):
    await self._session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": TOPIC_LOCK_KEY})
    
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

  async def unassign_all_topics(self, video_id: UUID):
    stmt = delete(VideoTopic).where(VideoTopic.video_id == video_id)
    await self._session.execute(stmt)
  
  async def assign_topic(self, topic_id: UUID, video_id: UUID, confidence: float) -> VideoTopic:
    stmt = (
      pg_insert(VideoTopic).
      values(topic_id=topic_id, video_id=video_id, confidence=confidence).
      on_conflict_do_update(   # type: ignore
        index_elements=[VideoTopic.topic_id, VideoTopic.video_id],
        set_={
          "created_at": func.now(),
          "confidence": confidence
        }
      ).
      returning(VideoTopic)
    )
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def search_topics(self, search_keywords: list[str]) -> Sequence[Topic]:
    if len(search_keywords) == 0:
      return []
    
    cleaned = [s.replace("-", "") for s in search_keywords]
    query_keywords = []
    for kw in cleaned:
      kw = kw.strip()
      if not kw:
        continue
      
      parts = [p for p in kw.split() if p]
      query_keywords.append(" & ".join(parts))
      
    if len(query_keywords) == 0:
      return []
        
    query_str = " | ".join(query_keywords)
    
    stmt = (
      select(Topic).
      where(func.to_tsquery('english', query_str).op('@@')(Topic.name_tsv)).
      order_by(func.ts_rank_cd(Topic.name_tsv, func.to_tsquery('english', query_str)).desc())
    )

    result = await self._session.execute(stmt)
    return result.scalars().all()
  
  async def get_total_videos_per_topic(self, author_id: UUID | None = None) -> list[TopicWithCount]:
    stmt = (
      select(
          Topic.id,
          Topic.name,
          func.count(Video.id).label("total_videos")
      ).
      select_from(Topic).
      join(VideoTopic, Topic.id == VideoTopic.topic_id, isouter=True).
      join(Video, Video.id == VideoTopic.video_id, isouter=True).
      group_by(Topic.id).
      order_by(func.count(Video.id).desc())
    )

    if author_id is not None:
      stmt = stmt.where(Video.author_id == author_id)
    
    result = await self._session.execute(stmt)
    return [
      TopicWithCount(id=row.id, name=row.name, total_videos=row.total_videos)
      for row in result
    ]
  
  async def commit(self):
    await self._session.commit()
