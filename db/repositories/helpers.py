from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from db.models import Video, AnnotationKind, MetaSource, VideoSource, VideoAnnotation


class VideoMeta(BaseModel):
  title: str | None
  description: str | None
  hashtags: list[str] | None
  topics: list[str] | None
  frame_content_type: list[str] | None
  frame_style: list[str] | None
  frame_quality: list[str] | None


class FrameData(BaseModel):
  frame_number: int
  time_sec: float
  description: str
  objects: list[str]
  actions: list[str]
  environment: str
  summary: str
  logos: list[str]


class VideoTranscription(BaseModel):
  text: str
  start_sec: float
  end_sec: float


class VideoContent(BaseModel):
  label: str | None
  synopsis: str | None
  actions: list[str] | None
  transcription: list[VideoTranscription] | None
  frames: list[FrameData] | None


class ProcessingData(BaseModel):
  revision: int
  extra_data: dict | None
  created_at: datetime
  updated_at: datetime
  processed_at: datetime | None
  processing_error: bool | None
  categorized_at: datetime | None
  categorization_error: bool | None
  challenges_created_at: datetime | None
  challenges_creating_error: bool | None


class TextVideoData(BaseModel):
  id: UUID
  url: str
  source: VideoSource
  meta: VideoMeta
  uploaded_at: datetime | None
  likes: int | None
  views: int | None
  comments: int | None
  content: VideoContent
  processing: ProcessingData | None


def full_video_data(video: Video, include_frames: bool = True, include_processing_data: bool = False) -> TextVideoData:
  video_meta = _get_post_meta(video)
  video_details = _get_video_details(video, include_frames)

  video_data = TextVideoData(
    id=video.id,
    url=video.url,
    source=video.source,
    meta=video_meta,
    uploaded_at=video.uploaded_at,
    likes=video.likes,
    views=video.views,
    comments=video.comments,
    content=video_details,
    processing=_get_video_processing_data(video) if include_processing_data else None
  )

  return video_data


def _get_video_processing_data(video: Video) -> ProcessingData:
  return ProcessingData(
    revision=video.revision,
    extra_data=video.extra_data,
    created_at=video.created_at,
    updated_at=video.updated_at,
    processed_at=video.processed_at,
    processing_error=video.processing_error,
    categorized_at=video.categorized_at,
    categorization_error=video.categorization_error,
    challenges_created_at=video.challenges_created_at,
    challenges_creating_error=video.challenges_creating_error
  )


def _get_post_meta(video: Video) -> VideoMeta:
  title: str | None = None
  description: str | None = None
  hashtags: list[str] = []
  topics: list[str] = []
  frame_content_type: set[str] = set()
  frame_style: set[str] = set()
  frame_quality: set[str] = set()

  for m in video.video_meta:
    if m.revision != video.revision:
      continue

    if m.source == MetaSource.title:
      title = m.value
    if m.source == MetaSource.description:
      description = m.value
    if m.source == MetaSource.hashtag:
      hashtags.append(m.value)
    if m.source == MetaSource.topic:
      topics.append(m.value)
    if m.source == MetaSource.frame_content_type:
      frame_content_type.add(m.value)
    if m.source == MetaSource.frame_style:
      frame_style.add(m.value)
    if m.source == MetaSource.frame_quality:
      frame_quality.add(m.value)

  return VideoMeta(
    title=title,
    description=description,
    hashtags=hashtags if len(hashtags) > 0 else None,
    topics=topics if len(topics) > 0 else None,
    frame_content_type=list(frame_content_type) if len(frame_content_type) else None,
    frame_style=list(frame_style) if len(frame_style) else None,
    frame_quality=list(frame_quality) if len(frame_quality) else None,
  )


def _get_video_details(video: Video, include_frames: bool) -> VideoContent:
  label: str | None = None
  synopsis: str | None = None
  actions: list[str] = []
  transcription: list[VideoTranscription] = []
  frames: dict[int, list[VideoAnnotation]] = {}
  frame_data: list[FrameData] = []

  for a in video.annotations:
    if a.revision != video.revision:
      continue

    if a.kind == AnnotationKind.label:
      label = a.value
    if a.kind == AnnotationKind.synopsis:
      synopsis = a.value
    if a.kind == AnnotationKind.action:
      actions.append(a.value)
    if a.kind == AnnotationKind.transcription:
      transcription.append(_get_video_transcription(a))
    if (a.kind == AnnotationKind.frame or
        a.kind == AnnotationKind.frame_object or
        a.kind == AnnotationKind.frame_action or
        a.kind == AnnotationKind.frame_environment or
        a.kind == AnnotationKind.frame_summary or
        a.kind == AnnotationKind.frame_logo):
      frame_number = _get_frame_number(a.meta)
      if frame_number >= 0:
        frame_data_list = frames.get(frame_number, [])
        frame_data_list.append(a)
        frames[frame_number] = frame_data_list

  if include_frames:
    for k, v in frames.items():
      frame_data.append(_process_frame(k, v))

  return VideoContent(
    label=label,
    synopsis=synopsis,
    actions=actions if len(actions) > 0 else None,
    transcription=sorted(transcription, key=lambda t: t.start_sec) if len(transcription) > 0 else None,
    frames=sorted(frame_data, key=lambda f: f.frame_number) if len(frame_data) > 0 else None
  )

def _get_video_transcription(annotation: VideoAnnotation) -> VideoTranscription:
  start_sec: float = 0
  end_sec: float = 0

  if annotation.meta:
    start_sec = annotation.meta.get("start_sec", 0)
    end_sec = annotation.meta.get("end_sec", 0)

  return VideoTranscription(text=annotation.value, start_sec=start_sec, end_sec=end_sec)


def _get_frame_number(meta: dict | None) -> int:
  if not meta:
    return -1

  return meta.get("frame_number", -1)

def _process_frame(frame_number: int, annotations: list[VideoAnnotation]) -> FrameData:
  description: str = "no description"
  objects: list[str] = []
  actions: list[str] = []
  environment: str = "no environment data"
  summary: str = "no summary data"
  logos: list[str] = []

  for a in annotations:
    if a.kind == AnnotationKind.frame:
      description = a.value
    if a.kind == AnnotationKind.frame_object:
      objects.append(a.value)
    if a.kind == AnnotationKind.frame_action:
      actions.append(a.value)
    if a.kind == AnnotationKind.frame_environment:
      environment = a.value
    if a.kind == AnnotationKind.frame_summary:
      summary = a.value
    if a.kind == AnnotationKind.frame_logo:
      logos.append(a.value)

  time_sec = 0
  if len(annotations) > 0 and annotations[0].meta:
    time_sec = annotations[0].meta.get("time_sec", 0)

  return FrameData(
    frame_number=frame_number,
    time_sec=time_sec,
    description=description,
    objects=objects,
    actions=actions,
    environment=environment,
    summary=summary,
    logos=logos
  )
