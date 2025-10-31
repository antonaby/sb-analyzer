from uuid import UUID

from fastapi import APIRouter, Query
from api.deps import *
from db.repositories.helpers import TextVideoData, full_video_data

router = APIRouter(
  prefix="/videos",
  tags=["videos"],
)


@router.get("/{video_id}", response_model_exclude_none=True)
async def get_video(
    video_id: UUID,
    video_repo: VideoRepository = Depends(get_video_repo)
) -> TextVideoData:
  video = await video_repo.get_video_by_id(
    video_id,
    with_annotations=True,
    with_meta=True,
    with_processing=True
  )

  return full_video_data(video, True, True)


@router.get("/")
async def search_videos(
    q: str = Query(default=None, min_length=1),
    with_scraped_data: bool = Query(False, description="Add data produced by a scrapper"),
    with_annotations: bool = Query(False, description="Add processed data for video"),
    with_meta: bool = Query(False, description="Add video meta"),
    db: AsyncSession = Depends(get_async_db)
):
  repo = VideoRepository(db)

  videos = await repo.search_videos(q, with_scraped_data, with_annotations, with_meta)

  return {
    "videos": videos
  }


