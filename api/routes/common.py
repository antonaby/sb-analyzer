from api.models import TopicsShort, VideoShort
from db.models import Video, AnnotationKind, MetaSource
from db.repositories.topics import TopicWithCount


def to_topic_short(t: TopicWithCount) -> TopicsShort:
  return TopicsShort(id=t["id"], name=t["name"], total_videos=t["total_videos"])


def to_topic_shorts(topics: list[TopicWithCount]) -> list[TopicsShort]:
  return [
    to_topic_short(t)
    for t in topics
  ]


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