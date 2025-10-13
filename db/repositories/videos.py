from typing import Any
from uuid import UUID

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, literal_column
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert


from db.models import Author, AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource


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


class VideoRepository:
  
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
    
  async def get_video_by_id(self, video_id: UUID, load_scraped_data: bool = True) -> Video | None:
    stmt = select(Video).where(Video.id == video_id)
    if load_scraped_data:
      stmt = stmt.options(joinedload(Video.scraped_data))
      
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
 