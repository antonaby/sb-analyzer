from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import or_, select, func, literal_column, desc, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy.sql.selectable import Select

from db.models import Author, AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource, \
  VideoSearch, Hashtag, VideoHashtag, VideoTopic
from db.repositories.common import BaseAsyncRepo


def prepare_meta(
  source: MetaSource,
  value: str,
  meta_data: dict = {}
) -> VideoMeta:
  meta = VideoMeta(
    source=source,
    value=value,
    meta=meta_data
  )
  
  return meta


def prepare_annotation(
  kind: AnnotationKind,
  value: str,
  meta: dict = {}
) -> VideoAnnotation:
  annotation = VideoAnnotation(
    kind=kind,
    value=value,
    meta=meta
  )
    
  return annotation


class VideoRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def upsert_video(
    self, 
    url: str, source: VideoSource, author: Author, 
    uploaded_at: datetime, likes: int, views: int, comments: int) -> tuple[Video, bool]:
    
    update_values: dict[str, Any] = {
      "updated_at": func.now(),
      "uploaded_at": uploaded_at,
      "likes": likes,
      "views": views,
      "comments": comments
    }

    stmt = (
      pg_insert(Video)
      .values(url=url, source=source, author_id=author.id, uploaded_at=uploaded_at, likes=likes, views=views, comments=comments)
      .on_conflict_do_update(   # type: ignore
        index_elements=[Author.url],
        set_=update_values
      )
      .returning(Video, literal_column("xmax"))    
    )
    
    result = await self._session.execute(stmt)
    row, xmax = result.first() # type: ignore
    video: Video = row
    is_new = xmax == 0

    return video, is_new

  async def add_scraped_data(self, video_id: UUID, data: dict) -> ScrapedData:
    stmt = pg_insert(ScrapedData).values(video_id=video_id, data=data).returning(ScrapedData)

    result = await self._session.execute(stmt)
    return result.scalar_one()
  
  async def add_search(self, search_id: UUID, video_id: UUID, is_new: bool) -> VideoSearch:
    stmt = (
      pg_insert(VideoSearch).
      values(search_id=search_id, video_id=video_id, is_new=is_new).
      on_conflict_do_update(   # type: ignore
        index_elements=[VideoSearch.search_id, VideoSearch.video_id],
        set_={
          "created_at": func.now(),
          "is_new": is_new
        }
      )
      .returning(VideoSearch)
    )
    
    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def get_video_by_topic(
      self,
      topic_id: UUID,
      load_annotations: bool = False,
      annotations_to_load: list[AnnotationKind] | None = None,
      load_meta: bool = False,
      meta_to_load: list[MetaSource] | None = None,
      max_videos: int = 100,
      uploaded_after: datetime | None = None,
      sort_desc: bool = True
  ) -> Sequence[Video]:
    sort_by = desc(Video.uploaded_at) if sort_desc else Video.uploaded_at

    conditions = [
      VideoTopic.topic_id == topic_id
    ]

    if uploaded_after:
      conditions.append(
        Video.uploaded_at >= uploaded_after
      )

    stmt = (
      select(Video).
      join(VideoTopic).
      where(*conditions).
      order_by(sort_by).
      limit(max_videos)
    )

    stmt = self._append_eager_loading(stmt, load_annotations, annotations_to_load, load_meta, meta_to_load)

    result = await self._session.execute(stmt)
    return result.scalars().all()
  
  async def get_videos_by_author(
    self, 
    author_id: UUID, 
    load_annotations: bool = False,
    annotations_to_load: list[AnnotationKind] | None = None,
    load_meta: bool = False,
    meta_to_load: list[MetaSource] | None = None,
    max_videos: int = 100,
    sort_desc: bool = True
  ) -> Sequence[Video]:
    sort_by = desc(Video.uploaded_at) if sort_desc else Video.uploaded_at
      
    stmt = (
      select(Video).
      where(Video.author_id == author_id).
      order_by(sort_by).
      limit(max_videos)
    )
    
    stmt = self._append_eager_loading(stmt, load_annotations, annotations_to_load, load_meta, meta_to_load)
    
    result = await self._session.execute(stmt)
    return result.scalars().all()

  @staticmethod
  def _append_eager_loading(
      stmt: Select,
      load_annotations: bool,
      annotations_to_load: list[AnnotationKind] | None,
      load_meta: bool,
      meta_to_load: list[MetaSource] | None,
  ) -> Select:
    if load_annotations:
      stmt = stmt.options(selectinload(Video.annotations))
      if annotations_to_load:
        stmt = stmt.options(
          with_loader_criteria(VideoAnnotation, VideoAnnotation.kind.in_(annotations_to_load))
        )

    if load_meta:
      stmt = stmt.options(selectinload(Video.video_meta))
      if meta_to_load:
        stmt = stmt.options(
          with_loader_criteria(VideoMeta, VideoMeta.source.in_(meta_to_load))
        )

    return stmt
    
  async def get_video_by_id(
    self, 
    video_id: UUID, 
    with_scraped_data: bool = False, 
    with_annotations: bool = False, 
    with_meta: bool = False
  ) -> Video | None:
    stmt = select(Video).where(Video.id == video_id)
    if with_scraped_data:
      stmt = stmt.options(selectinload(Video.scraped_data))
    if with_annotations:
      stmt = stmt.options(selectinload(Video.annotations))
    if with_meta:
      stmt = stmt.options(selectinload(Video.video_meta))
      
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def set_video_processing(self, video_id: UUID, with_error: bool):
    stmt = update(Video).where(Video.id == video_id).values(processed_at=func.now(), processing_error=with_error)
    await self._session.execute(stmt)

  async def set_video_categorization(self, video_id: UUID, with_error: bool):
    stmt = update(Video).where(Video.id == video_id).values(categorized_at=func.now(), categorization_error=with_error)
    await self._session.execute(stmt)

  async def upsert_hashtag(self, name: str, source: VideoSource) -> Hashtag:
    stmt = (
      pg_insert(Hashtag)
      .values(name=name, source=source)
      .on_conflict_do_update(  # type: ignore
        index_elements=[Hashtag.name, Hashtag.source],
        set_={
          "updated_at": func.now()
        }
      )
      .returning(Hashtag)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def assign_hashtag(self, video_id: UUID, hashtag_id: UUID) -> VideoHashtag:
    stmt = (
      pg_insert(VideoHashtag)
      .values(hashtag_id=hashtag_id, video_id=video_id)
      .on_conflict_do_update(  # type: ignore
        index_elements=[VideoHashtag.hashtag_id, VideoHashtag.video_id],
        set_={
          "created_at": func.now()
        }
      )
      .returning(VideoHashtag)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def search_videos(
      self,
      query: str,
      with_scraped_data: bool = False,
      with_annotations: bool = False,
      with_meta: bool = False
  ):
    ts_query = func.plainto_tsquery("english", query)
    
    stmt = (
      select(Video).
      join(Video.annotations).
      join(Video.video_meta).
      where(
        or_(
          VideoMeta.value_tsv.op("@@")(ts_query),
          VideoAnnotation.value_tsv.op("@@")(ts_query)
        )
      )
      .distinct()
    )

    if with_scraped_data:
      stmt = stmt.options(selectinload(Video.scraped_data))
    if with_annotations:
      stmt = stmt.options(selectinload(Video.annotations))
    if with_meta:
      stmt = stmt.options(selectinload(Video.video_meta))

    videos = await self._session.scalars(stmt)
    return videos.all()
  
  async def commit(self):
    await self._session.commit()
