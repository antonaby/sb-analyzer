from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource


def prepare_video(
  url: str, 
  source: VideoSource, 
  scraped_data: ScrapedData,
  extra_data: dict = {},
  annotations: list[VideoAnnotation] = [],
  video_meta: list[VideoMeta] = [],
) -> Video:
  video = Video(
    url=url,
    source=source,
    scraped_data=scraped_data,
    extra_data=extra_data,
    annotations=annotations,
    video_meta=video_meta
  )
  
  return video


def prepare_meta(
  source: MetaSource,
  value: str,
) -> VideoMeta:
  meta = VideoMeta(
    source=source,
    value=value
  )
  
  return meta


def prepare_scraped_data(data: dict = {}) -> ScrapedData:
  return ScrapedData(data=data)


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


class VideoRepository:
  
  def __init__(self, session: AsyncSession):
    self._session = session
  
  async def get_video_by_url(self, url: str) -> Video | None:
    stmt = select(Video).where(Video.url == url)
    result = await self._session.execute(stmt)
    
    return result.scalar_one_or_none()
  
  async def delete_video(self, video: Video):
    await self._session.delete(video)
