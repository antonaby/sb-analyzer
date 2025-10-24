from typing import Sequence, TypedDict
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, select, text, func, delete, Select, Result
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Topic, Video, VideoTopic, TopicTranslation
from db.repositories.common import BaseAsyncRepo, regconfig_for

TOPIC_LOCK_KEY: int = 1


class TopicWithVideoCount(BaseModel):
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

  async def get_all_topics(self) -> Sequence[Topic]:
    result = await self._session.execute(select(Topic))
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

  async def find_topics_without_challenges(self, min_videos: int) -> list[TopicWithVideoCount]:
    stmt = self._base_total_videos_query()
    stmt = stmt.where(Topic.last_challenges_created_at.is_(None))

    if min_videos:
      stmt = stmt.having(func.count(Video.id) >= min_videos)

    result = await self._session.execute(stmt)
    return self._parse_total_videos_result(result)

  async def get_total_videos_per_topic(self,
                                       author_id: UUID | None = None,
                                       min_videos: int = 0) -> list[TopicWithVideoCount]:
    stmt = self._base_total_videos_query()

    if author_id is not None:
      stmt = stmt.where(Video.author_id == author_id)

    if min_videos:
      stmt = stmt.having(func.count(Video.id) >= min_videos)

    result = await self._session.execute(stmt)
    return self._parse_total_videos_result(result)

  @staticmethod
  def _base_total_videos_query() -> Select:
    return (
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

  @staticmethod
  def _parse_total_videos_result(result: Result) -> list[TopicWithVideoCount]:
    return [
      TopicWithVideoCount(id=row.id, name=row.name, total_videos=row.total_videos)
      for row in result
    ]
  
  async def commit(self):
    await self._session.commit()
