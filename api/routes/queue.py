from fastapi import APIRouter
from api.deps import *
from api.models import VideoProcessingStatus, VideoProcessingDetails, UnprocessedVideos


router = APIRouter(
  prefix="/queue",
  tags=["queue"],
)


@router.get("/")
async def get_unprocessed_videos(video_repo: VideoRepository = Depends(get_video_repo)):
  videos = await video_repo.fetch_videos_under_processing()
  videos_short = [
    VideoProcessingStatus(
      id=v.id,
      url=v.url,
      jobs=[
        VideoProcessingDetails(
          job_id=j.job_id,
          source=j.source,
          created_at=j.created_at,
          started_at=j.started_at,
          finished_at=j.finished_at
        )
        for j in v.processing
      ]
    )
    for v in videos
  ]

  return UnprocessedVideos(
    total=len(videos_short),
    videos=videos_short
  )

