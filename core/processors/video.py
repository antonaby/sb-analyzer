import logging
from abc import ABC
from datetime import datetime, timezone
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent, VideoSummary
from core.agents.topic import TopicAgent, TopicProposal
from core.file import AudioFile, UrlVideoSource, VideoFile
from core.transcribe import AudioData, LemonfoxClient, Transcription
from core.video import ClipTaggerClient, VideoData, Frame
from db.models import Video, VideoAnnotation, AnnotationKind, VideoMeta, MetaSource, VideoProcessing
from db.repositories.topics import TopicRepository
from db.repositories.videos import prepare_meta, prepare_annotation, VideoRepository
from db.repositories.helpers import full_video_data
from models.common import PostDetails


class VideoProcessorError(Exception):
  pass


class BaseVideoProcessor(ABC):

  def __init__(self, async_session: async_sessionmaker[AsyncSession]):
    self._db = async_session

  async def _start_job(
      self, job_id: UUID,
      with_scraped_data: bool = False,
      with_annotations: bool = False,
      with_meta: bool = False
  ) -> tuple[Video, VideoProcessing]:
    async with self._db() as session:
      repo = VideoRepository(session)
      job = await repo.get_video_processing_by_id(job_id)
      if not job:
        raise VideoProcessorError(f"Video {job_id} not found")

      video = await repo.get_video_by_id(
        job.video_id,
        with_scraped_data=with_scraped_data,
        with_annotations=with_annotations,
        with_meta=with_meta
      )
      if not video:
        raise VideoProcessorError(f"Video {job.video_id} not found")

      job.started_at = datetime.now(timezone.utc)
      await session.commit()

      return video, job

  async def _set_error(self, job: VideoProcessing):
    try:
      async with self._db() as session:
        job = await session.merge(job, load=False)
        job.finished_at = datetime.now(timezone.utc)

        repo = VideoRepository(session)
        await repo.mark_processing_as_error(job.video_id)

        await session.commit()
    except Exception as e:
      pass


class ProcessedVideo(TypedDict):
  video_id: UUID
  processed_at_utc: datetime


class VideoProcessor(BaseVideoProcessor):
  
  def __init__(self,
               ct_client: ClipTaggerClient, lm_client: LemonfoxClient, agent: SummaryAgent,
               async_session: async_sessionmaker[AsyncSession],
               tmp_dir: str):

    super().__init__(async_session)
    self._log = logging.getLogger("app.videoprocessor")
    self._ct_client = ct_client
    self._lm_client = lm_client
    self._agent = agent
    self._tmp_dir = tmp_dir
    
  async def create_summary(
    self,
    job_id: UUID,
    delete_downloaded_files: bool = True
  ) -> ProcessedVideo:
    video_model, job_model = await self._start_job(job_id, with_scraped_data=True)
    video_model, job_model = await self._create_summary(video_model, job_model, delete_downloaded_files)
    
    return {
      "video_id": video_model.id,
      "processed_at_utc": job_model.finished_at,
    }
    
  async def _create_summary(
    self,
    video_model: Video,
    job_model: VideoProcessing,
    delete_downloaded_files: bool
  ) -> tuple[Video, VideoProcessing]:
    video_file = None
    video_source = None
    
    try:
      post_data = cast(PostDetails, video_model.scraped_data[0].data)
      video_source = await UrlVideoSource.new(post_data["download_url"], self._tmp_dir)
      
      video_file = VideoFile(video_source)  
      audio_file = AudioFile(video_source)
      
      video_data = VideoData(self._ct_client, video_file)
      audio_data = AudioData(self._lm_client, audio_file)
      
      summary = await self._agent.run(post_data, video_data, audio_data)
      return await self._save_video_details(video_model, job_model, post_data, video_data, audio_data, summary)
    except Exception as e:
      await self._set_error(job_model)
      raise VideoProcessorError("cannot create summary for a video") from e
    finally:
      try:
        if video_file is not None:
          video_file.close()
        if delete_downloaded_files and video_source is not None:
          video_source.delete()
      except Exception as e:
        self._log.exception(e)
        
  async def _save_video_details(
    self, 
    video_model: Video,
    job_model: VideoProcessing,
    post_data: PostDetails, video_data: VideoData, 
    audio_data: AudioData, summary: VideoSummary
  ) -> tuple[Video, VideoProcessing]:

    processed_frames = await video_data.get_processed_frames()
    transcriptions = audio_data.get_processed_transcriptions()
    
    annotations, video_meta = _create_video_data(
      post_data, summary, processed_frames, transcriptions
    )
    
    async with self._db() as session:
      video_model = await session.merge(video_model, load=False)
      revision = video_model.revision + 1

      video_repo = VideoRepository(session)
      await video_repo.delete_old_data(video_model.id)

      video_model.revision = revision
      video_model.extra_data = {
        "duration": video_data.get_duration(),
        "frames": video_data.get_total_frames()
      }
      video_model.processing_error = False
      video_model.processed_at = datetime.now(timezone.utc)

      for annotation in annotations:
        annotation.video_id = video_model.id
        annotation.revision = revision
      session.add_all(annotations)
        
      for meta in video_meta:
        meta.video_id = video_model.id
        meta.revision = revision
      session.add_all(video_meta)

      job_model = await session.merge(job_model, load=False)
      job_model.finished_at = datetime.now(timezone.utc)
      job_model.processing_error = False

      await session.commit()
      
      return video_model, job_model
      

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
  annotations: list[VideoAnnotation] = [
    prepare_annotation(
      kind=AnnotationKind.label,
      value=summary.label
    ),
    prepare_annotation(
      kind=AnnotationKind.synopsis,
      value=summary.synopsis
    )
  ]

  for action in summary.actions:
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.action,
        value=action
      )
    )
  
  return annotations


def _create_summary_meta(summary: VideoSummary) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  for topic in summary.topics:
    video_meta.append(
      prepare_meta(MetaSource.topic, topic)
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
  
  for frame_object in frame.objects:
    _append_frame_ann(annotations, AnnotationKind.frame_object, frame_object, frame)

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


class AssignedTopic(TypedDict):
  topic_id: UUID
  is_new: bool
  name: str
  confidence: float


class TopicProcessorResult(TypedDict):
  video_id: UUID
  topics: list[AssignedTopic]


class TopicProcessorError(Exception):
  pass


class TopicProcessor(BaseVideoProcessor):

  def __init__(self, topic_agent: TopicAgent, async_session: async_sessionmaker[AsyncSession]):
    super().__init__(async_session)
    self._topic_agent = topic_agent

  async def identify_topics(self, job_id: UUID) -> TopicProcessorResult:
    video, job = await self._start_job(job_id, with_scraped_data=True, with_annotations=True, with_meta=True)
    video_data = full_video_data(video)

    try:
      topics = await self._topic_agent.run(video_data)
      return await self._save_topics(video, topics, job)
    except Exception as e:
      await self._set_error(job)
      raise VideoProcessorError("cannot create summary for a video") from e

  async def _save_topics(self, video: Video, topics: list[TopicProposal], job: VideoProcessing) -> TopicProcessorResult:
    async with self._db() as session:
      video = await session.merge(video, load=False)
      topic_repo = TopicRepository(session)
      assigned_topics: list[AssignedTopic] = []

      for t in topics:
        topic = await topic_repo.get_topic(t.id) if t.id else None
        if not topic:
          topic = await topic_repo.create_topic(t.name)

        await topic_repo.assign_topic(topic.id, video.id, t.confidence)
        assigned_topics.append({
          "topic_id": topic.id,
          "is_new": t.is_new,
          "name": t.name,
          "confidence": t.confidence
        })

      job_model = await session.merge(job, load=False)
      job_model.finished_at = datetime.now(timezone.utc)
      job_model.processing_error = False

      await session.commit()
      return {
        "video_id": video.id,
        "topics": assigned_topics,
      }