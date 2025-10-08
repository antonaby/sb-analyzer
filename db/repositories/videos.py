from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AnnotationKind, Video, VideoAnnotation, VideoSource


class VideoRepository:
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def create_video(
    self, 
    url: str, download_url: str, source: VideoSource, 
    title: str = "", author: str = "", duration_seconds: int = 0, 
    meta: dict = {},
    commit: bool = False
  ) -> Video:
    video = Video(
      url=url,
      download_url=download_url,
      source=source,
      title=title,
      author=author,
      duration_seconds=duration_seconds,
      meta=meta
    )
    
    self._session.add(video)
    
    if commit:
      await self._session.commit()
    
    return video
  
  async def create_annotation(
    self, 
    video_id: UUID,
    kind: AnnotationKind,
    value: str,
    meta: dict = {},
    commit: bool = False) -> VideoAnnotation:
    annotation = VideoAnnotation(
      video_id=video_id,
      kind=kind,
      value=value,
      meta=meta
    )
    
    self._session.add(annotation)
    
    if commit:
      await self._session.commit()
      
    return annotation
  