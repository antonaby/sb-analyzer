from typing import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import insert, select, func, delete, Select, Result
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Topic, Video, VideoTopic, TopicTranslation, ChallengeTopic, TopicGroup
from db.repositories.common import BaseAsyncRepo, regconfig_for


class TopicWithVideoCount(BaseModel):
  id: UUID
  name: str
  videos: int
  challenges: int


class TopicRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session

  async def create_topic_group(self, name: str) -> TopicGroup:
    stmt = insert(TopicGroup).values(name=name).returning(TopicGroup)
    result = await self._session.execute(stmt)

    return result.scalar_one()

  async def create_topic(self, name: str, group_id: UUID) -> Topic:
    stmt = insert(Topic).values(name=name, group_id=group_id).returning(Topic)
    result = await self._session.execute(stmt)
    
    return result.scalar_one()
  
  async def get_topic(self, topic_id: UUID, with_translations: bool = False) -> Topic | None:
    stmt = select(Topic).where(Topic.id == topic_id)

    if with_translations:
      stmt = stmt.options(joinedload(Topic.translations))

    result = await self._session.execute(stmt)
    return result.unique().scalar_one_or_none()

  async def get_all_topics(self, group_id: UUID) -> Sequence[Topic]:
    stmt = select(Topic).where(Topic.group_id == group_id)

    result = await self._session.execute(stmt)
    return result.scalars().all()

  async def unassign_all_topics(self, video_id: UUID, topic_group_id: UUID):
    sub_query = (
      select(Topic.id)
      .where(Topic.group_id == topic_group_id)
      .scalar_subquery()
    )

    stmt = (
      delete(VideoTopic)
      .where(
        VideoTopic.video_id == video_id,
        VideoTopic.topic_id.in_(sub_query)
      )
    )

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

  async def get_total_videos_per_topic(self,
                                       author_id: UUID | None = None,
                                       min_videos: int = 0) -> list[TopicWithVideoCount]:
    stmt = self._base_total_videos_query()

    if author_id is not None:
      stmt = stmt.where(Video.author_id == author_id)

    if min_videos:
      stmt = stmt.having(func.count(VideoTopic.video_id) >= min_videos)

    result = await self._session.execute(stmt)
    return self._parse_total_videos_result(result)

  @staticmethod
  def _base_total_videos_query() -> Select:
    video_counts = (
      select(VideoTopic.topic_id, func.count().label("total_videos")).
      group_by(VideoTopic.topic_id).
      subquery()
    )

    challenge_counts = (
      select(ChallengeTopic.topic_id, func.count().label("total_challenges")).
      group_by(ChallengeTopic.topic_id).
      subquery()
    )

    return (
      select(
        Topic.id,
        Topic.name,
        video_counts.c.total_videos,
        challenge_counts.c.total_challenges,
      ).
      join(video_counts, video_counts.c.topic_id == Topic.id, isouter=True).
      join(challenge_counts, challenge_counts.c.topic_id == Topic.id, isouter=True).
      order_by(video_counts.c.total_videos.desc().nullslast())
    )

  @staticmethod
  def _parse_total_videos_result(result: Result) -> list[TopicWithVideoCount]:
    return [
      TopicWithVideoCount(
        id=row.id,
        name=row.name,
        videos=row.total_videos if row.total_videos else 0,
        challenges=row.total_challenges if row.total_challenges else 0
      )
      for row in result
    ]
  
  async def commit(self):
    await self._session.commit()
