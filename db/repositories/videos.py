from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert


from db.models import Author, AnnotationKind, Video, VideoAnnotation, VideoMeta, ScrapedData, VideoSource, MetaSource


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
    
  async def upsert_author(self, url: str, source: VideoSource) -> tuple[Author, bool]:
    stmt = (
      pg_insert(Author)
      .values(url=url, source=source)
      .on_conflict_do_update(   # type: ignore
        index_elements=[Author.url],
        set_={
          "updated_at": func.now()
        }
      )
      .returning(Author, literal_column("xmax"))
    ) 
   
    result = await self._session.execute(stmt)
    row, xmax = result.first() # type: ignore
    author: Author = row
    is_new = xmax == 0
    
    return author, is_new
  
  async def upsert_video(self, url: str, source: VideoSource, author: Author) -> tuple[Video, bool]:
    stmt = (
      pg_insert(Video)
      .values(url=url, source=source, author_id=author.id)
      .on_conflict_do_update(   # type: ignore
        index_elements=[Author.url],
        set_={
          "updated_at": func.now()
        }
      )
      .returning(Video, literal_column("xmax"))    
    )
    
    result = await self._session.execute(stmt)
    row, xmax = result.first() # type: ignore
    video: Video = row
    is_new = xmax == 0

    return video, is_new
    
  async def get_video_by_url(self, url: str) -> Video | None:
    stmt = select(Video).where(Video.url == url)
    result = await self._session.execute(stmt)
    
    return result.scalar_one_or_none()
  
  async def delete_video(self, video: Video):
    await self._session.delete(video)

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
 