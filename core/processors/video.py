import logging
from typing import TypedDict, cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid import UUID
from datetime import datetime, timezone

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient, Transcription
from core.agents.video import ClipTaggerClient, VideoData, Frame
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import Video, VideoAnnotation, AnnotationKind, VideoMeta, MetaSource
from db.repositories.videos import prepare_meta, prepare_annotation, VideoRepository
from models.common import PostDetails, VideoSummary


class VideoProcessorError(Exception):
  pass


class ProcessedVideo(TypedDict):
  video_id: UUID | None
  processed_at_utc: datetime | None


class VideoProcessor:
  
  def __init__(
    self, 
    ct_client: ClipTaggerClient, 
    lm_client: LemonfoxClient, 
    agent: SummaryAgent, 
    async_session: async_sessionmaker[AsyncSession],
    tmp_dir: str
  ):
    self._log = logging.getLogger("app.videoprocessor")
    self._ct_client = ct_client
    self._lm_client = lm_client
    self._agent = agent
    self._db = async_session
    self._tmp_dir = tmp_dir
    
  async def run(
    self, 
    video_id: UUID, 
    delete_downloaded_files: bool = True
  ) -> ProcessedVideo:
    video_model = await self._find_video(video_id)
    
    if video_model is None:
      self._log.warning(f"Video not found: {video_id}")
      return {
        "video_id": None,
        "processed_at_utc": None
      }
    
    video_model = await self._create_summary(video_model, delete_downloaded_files)
    
    return {
      "video_id": video_model.id,
      "processed_at_utc": video_model.processed_at
    }
        
  async def _find_video(self, video_id: UUID) -> Video | None:
    async with self._db() as session:
      repo = VideoRepository(session)
      return await repo.get_video_by_id(video_id)
    
  async def _create_summary(
    self,
    video_model: Video,
    delete_downloaded_files: bool
  ) -> Video:
    post_data = cast(PostDetails, video_model.scraped_data.data)
    video_source = await UrlVideoSource.new(post_data["download_url"], self._tmp_dir)
    
    video_file = VideoFile(video_source)  
    audio_file = AudioFile(video_source)
    
    video_data = VideoData(self._ct_client, video_file)
    audio_data = AudioData(self._lm_client, audio_file)
    
    try:
      summary = await self._agent.summary(post_data, video_data, audio_data)
      return await self._save_video_details(video_model, post_data, video_data, audio_data, summary)
    except Exception as e:
      raise VideoProcessorError("cannot create summary for a video") from e
    finally:
      try:
        video_file.close()
        if delete_downloaded_files:
          video_source.delete()
      except Exception as e:
        self._log.exception(e)
        
  async def _save_video_details(
    self, 
    video_model: Video,
    post_data: PostDetails, video_data: VideoData, 
    audio_data: AudioData, summary: VideoSummary
  ) -> Video:
    processed_frames = await video_data.get_processed_frames()
    transcriptions = audio_data.get_processed_transcriptions()
    
    annotations, video_meta = _create_video_data(
      post_data, summary, processed_frames, transcriptions
    )
    
    async with self._db() as session:
      video_model = await session.merge(video_model, load=False)
      
      for annotation in annotations:
        annotation.video_id = video_model.id
      
      session.add_all(annotations)
        
      for meta in video_meta:
        meta.video_id = video_model.id
      
      session.add_all(video_meta)

      video_model.extra_data = {
        "duration": video_data.get_duration(),
        "frames": video_data.get_total_frames()
      }
      video_model.processed_at = datetime.now(timezone.utc)
      
      await session.commit()
      return video_model
      

def _create_video_data(
  post: PostDetails, summary: VideoSummary, 
  frames: list[Frame], transcriptions: list[Transcription]
) -> tuple[list[VideoAnnotation], list[VideoMeta]]:
  annotations: list[VideoAnnotation] = _create_summary_annotations(summary)
  video_meta: list[VideoMeta] = _create_summary_meta(summary)
  
  annotations.extend(
    _create_transcribe_annotations(transcriptions)
  )
  
  for frame in frames:
    annotations.extend(_create_frame_annotations(frame))
    video_meta.extend(_create_frame_video_meta(frame))
        
  video_meta.extend(_create_post_meta(post))
  
  return annotations, video_meta


def _create_summary_annotations(summary: VideoSummary) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  annotations.append(
    prepare_annotation(
      kind=AnnotationKind.summary,
      value=summary.main_idea
    )
  )
      
  for synopsis in summary.synopsis:
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.summary_synopsis,
        value=synopsis
      )
    )
  
  return annotations


def _create_summary_meta(summary: VideoSummary) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  for theme in summary.theme:
    video_meta.append(
      prepare_meta(MetaSource.summary, theme)
    )  
  
  for video_type in summary.video_type:
    video_meta.append(
      prepare_meta(MetaSource.summary_video_type, video_type)
    ) 
  
  return video_meta


def _create_transcribe_annotations(transcriptions: list[Transcription]) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  for segment in transcriptions:
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.transcription,
        value=segment.text,
        meta={
          "start_sec": segment.start_sec,
          "end_sec": segment.end_sec
        }
      )
    )
  
  return annotations


def _create_post_meta(post: PostDetails) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  if post.get("title"):
    video_meta.append(
      prepare_meta(MetaSource.title, post.get("title"))
    )
    
  if post.get("description"):
    video_meta.append(
      prepare_meta(MetaSource.title, post.get("description"))
    )
  
  for hash_tag in post.get("hashtags", []):
    video_meta.append(
      prepare_meta(MetaSource.hashtag, hash_tag)
    )
  
  return video_meta


def _create_frame_video_meta(frame: Frame) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  meta_data = _get_frame_meta(frame)
  
  video_meta.append(
    prepare_meta(MetaSource.frame_content_type, frame.content_type, meta_data)
  )
  video_meta.append(
    prepare_meta(MetaSource.frame_style, frame.specific_style, meta_data)
  )
  video_meta.append(
    prepare_meta(MetaSource.frame_quality, frame.production_quality, meta_data)
  )
  
  return video_meta
  

def _create_frame_annotations(frame: Frame) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  _append_frame_ann(annotations, AnnotationKind.frame, frame.description, frame)
  _append_frame_ann(annotations, AnnotationKind.frame_environment, frame.environment, frame)
  _append_frame_ann(annotations, AnnotationKind.frame_summary, frame.summary, frame)
  
  for object in frame.objects:
    _append_frame_ann(annotations, AnnotationKind.frame_object, object, frame)

  for action in frame.actions:
    _append_frame_ann(annotations, AnnotationKind.frame_action, action, frame)

  for logo in frame.logos:
    _append_frame_ann(annotations, AnnotationKind.frame_logo, logo, frame)
  
  return annotations


def _append_frame_ann(annotations: list[VideoAnnotation], kind: AnnotationKind, value: str, frame: Frame):
  annotations.append(prepare_annotation(
    kind=kind,
    value=value,
    meta=_get_frame_meta(frame)
  ))


def _get_frame_meta(frame: Frame) -> dict:
  return {
    "frame_number": frame.frame_number,
    "time_sec": frame.time_sec
  }
