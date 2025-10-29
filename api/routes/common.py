from pydantic import BaseModel

from api.models import VideoShort
from db.models import Video, AnnotationKind, MetaSource


class OkResponse(BaseModel):
  result: bool
  msg: str


class CeleryJobDetails(BaseModel):
  celery_job_id: str
  celery_job_status: str


def to_video_short(video: Video) -> VideoShort:
  title = "no title"
  label = "no label"
  synopsis = "no synopsis"
  hashtags = []

  for annotation in video.annotations:
    if annotation.kind == AnnotationKind.label:
      label = annotation.value
    if annotation.kind == AnnotationKind.synopsis:
      synopsis = annotation.value

  for meta in video.video_meta:
    if meta.source == MetaSource.title:
      title = meta.value
    if meta.source == MetaSource.hashtag:
      hashtags.append(meta.value)

  return VideoShort(
    id=video.id,
    url=video.url,
    source=video.source,
    title=title,
    uploaded_at=video.uploaded_at,
    likes=video.likes,
    views=video.views,
    comments=video.comments,
    hashtags=hashtags,
    label=label,
    synopsis=synopsis
  )


def to_video_shorts(videos: list[Video]) -> list[VideoShort]:
  return [
    to_video_short(v)
    for v in videos
  ]