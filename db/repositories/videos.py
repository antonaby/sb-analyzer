from typing import Any, Sequence, TypedDict
from uuid import UUID

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, literal_column, desc
from sqlalchemy.orm import joinedload, selectinload, with_loader_criteria
from sqlalchemy.dialects.postgresql import insert as pg_insert


from db.models import Author, AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource, VideoSearch
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


def prepare_scraped_data(data: dict = {}) -> ScrapedData:
  return ScrapedData(data=data)


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
    sort_desc: bool = True
  ) -> Sequence[Video]:
    
    sort_by = desc(Video.uploaded_at) if sort_desc else Video.uploaded_at
    stmt = (
      select(Video).
      where(Video.author_id == author_id).
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
      stmt = stmt.options(joinedload(Video.scraped_data))
    if with_annotations:
      stmt = stmt.options(selectinload(Video.annotations))
    if with_meta:
      stmt = stmt.options(selectinload(Video.video_meta))
      
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


class VideoDataLoader:
  
  def __init__(self, author_id: UUID, video_repo: VideoRepository):
    self._author_id = author_id
    self._video_repo = video_repo

  async def load_video_data(self, max_videos: int = 100) -> list[VideoData]:
    videos = await self._video_repo.get_videos_by_author(
      self._author_id, 
      load_annotations=True, 
      annotations_to_load=[
        AnnotationKind.summary, 
        AnnotationKind.summary_synopsis, 
        AnnotationKind.transcription
      ],
      load_meta=True, 
      meta_to_load=[
        MetaSource.summary, 
        MetaSource.summary_video_type,
        MetaSource.title, 
        MetaSource.description, 
        MetaSource.hashtag
      ],
      max_videos=max_videos
    )
    
    video_data_list: list[VideoData] = []
    for video in videos:
      title, description, hashtags = self._get_post_meta(video)
      meta_summary, meta_summary_video_type = self._get_video_meta(video)
      summary, summary_synopsis, transcription = self._get_video_summary(video)
      
      video_data: VideoData = {
        "video_id": video.id,
        "source": video.source.value,
        "uploaded_at_iso": video.uploaded_at,
        "title": title,
        "description": description,
        "likes": video.likes,
        "views": video.views,
        "comments": video.comments,
        "hashtags": hashtags, 
        "meta_summary": meta_summary,
        "meta_summary_video_type": meta_summary_video_type, 
        "summary": summary,
        "summary_synopsis": summary_synopsis,
        "transcription": transcription
      }
    
      video_data_list.append(video_data)
    
    return video_data_list

  def _get_post_meta(self, video: Video) -> tuple[str, str, list[str]]:
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
  
  def _get_video_meta(self, video: Video) -> tuple[list[str], list[str]]:
    summary: list[str] = []
    summary_video_type: list[str] = []
    
    for m in video.video_meta:
      if m.source == MetaSource.summary:
        summary.append(m.value)
      if m.source == MetaSource.summary_video_type:
        summary_video_type.append(m.value)
    
    return summary, summary_video_type

  def _get_video_summary(self, video: Video) -> tuple[str, list[str], list[str]]:
    summary: str = "no summary"
    summary_synopsis: list[str] = []
    transcription: list[str] = []
    
    for a in video.annotations:
      if a.kind == AnnotationKind.summary:
        summary = a.value
      if a.kind == AnnotationKind.summary_synopsis:
        summary_synopsis.append(a.value)
      if a.kind == AnnotationKind.transcription:
        transcription.append(a.value)
        
    return summary, summary_synopsis, transcription
    
    
