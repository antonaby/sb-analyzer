from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import or_, select, func, literal_column, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from db.models import Author, AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource, \
  VideoSearch, VideoProcessing, VideoProcessingKind
from db.repositories.common import BaseAsyncRepo
from models.common import VideoData


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


def prepare_scraped_data(video_id: UUID, data: dict = {}) -> ScrapedData:
  return ScrapedData(video_id=video_id, data=data)


class VideoRepository(BaseAsyncRepo):
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def upsert_author(
    self, 
    url: str, source: VideoSource, 
    verified: bool | None, followers: int | None, total_videos: int | None) -> tuple[Author, bool]:
    
    update_values: dict[str, Any] = { "updated_at": func.now() }

    if verified is not None:
      update_values["verified"] = verified
    if followers is not None:
      update_values["followers"] = followers
    if total_videos is not None:
      update_values["total_videos"] = total_videos
    
    stmt = (
      pg_insert(Author)
      .values(url=url, source=source, verified=verified, followers=followers, total_videos=total_videos)
      .on_conflict_do_update(   # type: ignore
        index_elements=[Author.url],
        set_=update_values
      )
      .returning(Author, literal_column("xmax"))
    ) 
   
    result = await self._session.execute(stmt)
    row, xmax = result.first() # type: ignore
    author: Author = row
    is_new = xmax == 0
    
    return author, is_new
  
  async def fetch_unprocessed_videos(self) -> Sequence[Video]:
    stmt = select(Video).where(Video.processed_at.is_(None))
    result = await self._session.execute(stmt)
    return result.scalars().all()
  
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
  
  async def get_videos_by_author(
    self, 
    author_id: UUID, 
    load_annotations: bool = False,
    annotations_to_load: list[AnnotationKind] = [],
    load_meta: bool = False,
    meta_to_load: list[MetaSource] = [],
    max_videos: int = 100,
    sort_desc: bool = True,
    include_processing_errors: bool = False
  ) -> Sequence[Video]:
    sort_by = desc(Video.uploaded_at) if sort_desc else Video.uploaded_at
    conditions = [Video.author_id == author_id]
    if not include_processing_errors:
      conditions.append(or_(Video.processing_error.is_(False), Video.processing_error.is_(None)))
      
    stmt = (
      select(Video).
      where(*conditions).
      order_by(sort_by).
      limit(max_videos)
    )
    
    if load_annotations:
      stmt = stmt.options(selectinload(Video.annotations))
      if len(annotations_to_load) > 0:
        stmt = stmt.options(
          with_loader_criteria(VideoAnnotation, VideoAnnotation.kind.in_(annotations_to_load))
        )
    
    if load_meta:
      stmt = stmt.options(selectinload(Video.video_meta))
      if len(meta_to_load) > 0:
        stmt = stmt.options(
          with_loader_criteria(VideoMeta, VideoMeta.source.in_(meta_to_load))
        )
    
    result = await self._session.execute(stmt)
    return result.scalars().all()
    
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

  async def create_video_processing(self, video_id: UUID, source: VideoProcessingKind) -> VideoProcessing:
    stmt = (
      pg_insert(VideoProcessing).
      values(video_id=video_id, source=source).
      returning(VideoProcessing)
    )

    result = await self._session.execute(stmt)
    return result.scalar_one()

  async def get_video_processing_by_id(self, job_id: UUID) -> VideoProcessing | None:
    stmt = (
      select(VideoProcessing).
      where(VideoProcessing.id == job_id)
    )
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()

  async def find_videos(self, q: str):
    ts_query = func.plainto_tsquery("english", q)
    
    stmt = (
      select(Video)
      .join(Video.annotations)  # join VideoAnnotation
      .where(VideoAnnotation.value_tsv.op("@@")(ts_query))
      .distinct()  # avoid duplicates if multiple annotations match
    )

    videos = await self._session.scalars(stmt)
    return videos.all()
  
  async def commit(self):
    await self._session.commit()


def _get_video_summary(video: Video) -> tuple[str, str, list[str], list[str]]:
  label: str = "no label"
  synopsis: str = "no synopsis"
  actions: list[str] = []
  transcription: list[str] = []

  for a in video.annotations:
    if a.kind == AnnotationKind.label:
      label = a.value
    if a.kind == AnnotationKind.synopsis:
      synopsis = a.value
    if a.kind == AnnotationKind.action:
      actions.append(a.value)
    if a.kind == AnnotationKind.transcription:
      transcription.append(a.value)

  return label, synopsis, actions, transcription


def _get_video_meta(video: Video) -> list[str]:
  topics: list[str] = []

  for m in video.video_meta:
    if m.source == MetaSource.topic:
      topics.append(m.value)

  return topics


def _get_post_meta(video: Video) -> tuple[str, str, list[str]]:
  title: str = "no title"
  description: str = "no description"
  hashtags: list[str] = []

  for m in video.video_meta:
    if m.source == MetaSource.title:
      title = m.value
    if m.source == MetaSource.description:
      description = m.value
    if m.source == MetaSource.hashtag:
      hashtags.append(m.value)

  return title, description, hashtags


def get_video_data(video: Video) -> VideoData:
  title, description, hashtags = _get_post_meta(video)
  topics = _get_video_meta(video)
  label, synopsis, actions, transcription = _get_video_summary(video)

  video_data: VideoData = {
    "video_id": str(video.id),
    "source": video.source.value,
    "uploaded_at_iso": video.uploaded_at.isoformat(),
    "title": title,
    "description": description,
    "likes": video.likes,
    "views": video.views,
    "comments": video.comments,
    "hashtags": hashtags,
    "topics": topics,
    "label": label,
    "synopsis": synopsis,
    "actions": actions,
    "transcription": transcription
  }

  return video_data
