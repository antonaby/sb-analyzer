from uuid import UUID

from fastapi import APIRouter, Query
from api.deps import *


router = APIRouter(
  prefix="/videos",
  tags=["videos"],
)


@router.get("/{video_id}")
async def get_video(
  video_id: UUID,
  with_scraped_data: bool = Query(False, description="Add data produced by a scrapper"),
  with_annotations: bool = Query(False, deprecated="Add processed data for video"),
  with_meta: bool = Query(False, description="Add video meta"),
  video_repo: VideoRepository = Depends(get_video_repo)
):
  video = await video_repo.get_video_by_id(
    video_id,
    with_scraped_data=with_scraped_data,
    with_annotations=with_annotations,
    with_meta=with_meta
  )
  return video


@router.get("/")
async def search_videos(
    q: str = Query(default=None, min_length=1),
    with_scraped_data: bool = Query(False, description="Add data produced by a scrapper"),
    with_annotations: bool = Query(False, deprecated="Add processed data for video"),
    with_meta: bool = Query(False, description="Add video meta"),
    db: AsyncSession = Depends(get_async_db)
):
  repo = VideoRepository(db)

  videos = await repo.search_videos(q, with_scraped_data, with_annotations, with_meta)

  return {
    "videos": videos
  }


