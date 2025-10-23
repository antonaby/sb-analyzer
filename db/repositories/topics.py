from typing import Sequence, TypedDict
from uuid import UUID

from sqlalchemy import insert, select, text, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Topic, Video, VideoTopic, TopicTranslation
from db.repositories.common import BaseAsyncRepo, regconfig_for

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
  
  async def get_topic(self, topic_id: UUID, with_translations: bool = False) -> Topic | None:
    stmt = select(Topic).where(Topic.id == topic_id)

    if with_translations:
      stmt = stmt.options(joinedload(Topic.translations))

    result = await self._session.execute(stmt)
    return result.unique().scalar_one_or_none()

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

  async def create_translation(self, topic_id: UUID, lang: str, value: str) -> TopicTranslation:
    stmt = (
      insert(TopicTranslation).
      values(
        topic_id=topic_id,
        lang=lang,
        value=value,
        value_tsv=func.to_tsvector(regconfig_for(lang), value)
      ).
      returning(TopicTranslation)
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
