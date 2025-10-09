from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnnotationKind, Video, VideoAnnotation, VideoSource


def prepare_video(
  url: str, download_url: str, source: VideoSource, 
  title: str = "", author: str = "", duration_seconds: int = 0, 
  meta: dict = {},
  annotations: list[VideoAnnotation] = []
) -> Video:
  video = Video(
    url=url,
    download_url=download_url,
    source=source,
    title=title,
    author=author,
    duration_seconds=duration_seconds,
    meta=meta,
    annotations=annotations
  )
  
  return video

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
  