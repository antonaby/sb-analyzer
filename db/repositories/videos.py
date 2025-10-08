from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Video, VideoSource


class VideoRepository:
  
  def __init__(self, session: AsyncSession):
    self._session = session
    
  async def create_video(
    self, 
    url: str, download_url: str, source: VideoSource, 
    title: str = "", author: str = "", duration_seconds: int = 0, 
    meta: dict = {}
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
    await self._session.commit()
    
    return video