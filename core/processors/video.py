import logging
from typing import TypedDict, cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from uuid import UUID
from datetime import datetime, timezone

from core.agents.series import VideoSeriesAgent
from core.agents.summary import SummaryAgent, VideoSummary
from core.transcribe import AudioData, LemonfoxClient, Transcription
from core.video import ClipTaggerClient, VideoData, Frame
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import Topic, Video, VideoAnnotation, AnnotationKind, VideoMeta, MetaSource
from db.repositories.videos import prepare_meta, prepare_annotation, VideoRepository, VideoDataLoader
from db.repositories.topics import TopicRepository
from models.common import PostDetails


class VideoProcessorError(Exception):
  pass


class AssignedTopic(TypedDict):
  topic_id: UUID
  is_new: bool
  name: str
  confidence: float


class ProcessedVideo(TypedDict):
  video_id: UUID | None
  processed_at_utc: datetime | None
  assigned_topics: list[AssignedTopic]


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
        "processed_at_utc": None,
        "assigned_topics": []
      }
    
    video_model, topics = await self._create_summary(video_model, delete_downloaded_files)
    
    return {
      "video_id": video_model.id,
      "processed_at_utc": video_model.processed_at,
      "assigned_topics": topics
    }
        
  async def _find_video(self, video_id: UUID) -> Video | None:
    async with self._db() as session:
      repo = VideoRepository(session)
      return await repo.get_video_by_id(video_id, with_scraped_data=True)
    
  async def _create_summary(
    self,
    video_model: Video,
    delete_downloaded_files: bool
  ) -> tuple[Video, list[AssignedTopic]]:
    video_file = None
    video_source = None
    
    try:
      post_data = cast(PostDetails, video_model.scraped_data.data)
      video_source = await UrlVideoSource.new(post_data["download_url"], self._tmp_dir)
      
      video_file = VideoFile(video_source)  
      audio_file = AudioFile(video_source)
      
      video_data = VideoData(self._ct_client, video_file)
      audio_data = AudioData(self._lm_client, audio_file)
      
      summary = await self._agent.run(post_data, video_data, audio_data)
      return await self._save_video_details(video_model, post_data, video_data, audio_data, summary)
    except Exception as e:
      await self._set_error(video_model)
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
    post_data: PostDetails, video_data: VideoData, 
    audio_data: AudioData, summary: VideoSummary
  ) -> tuple[Video, list[AssignedTopic]]:
    processed_frames = await video_data.get_processed_frames()
    transcriptions = audio_data.get_processed_transcriptions()
    
    annotations, video_meta = _create_video_data(
      post_data, summary, processed_frames, transcriptions
    )
    
    async with self._db() as session:
      video_model = await session.merge(video_model, load=False)
      revision = video_model.revision + 1
      
      video_model.revision = revision
      video_model.extra_data = {
        "duration": video_data.get_duration(),
        "frames": video_data.get_total_frames()
      }
      video_model.processing_error = False
      video_model.processed_at = datetime.now(timezone.utc)
      
      topics = await _assign_topics(session, summary, video_model)
      
      for annotation in annotations:
        annotation.video_id = video_model.id
        annotation.revision = revision
      session.add_all(annotations)
        
      for meta in video_meta:
        meta.video_id = video_model.id
        meta.revision = revision
      session.add_all(video_meta)

      await session.commit()
      
      return video_model, topics
    
  async def _set_error(self, video_model: Video):
    async with self._db() as session:
      video_model = await session.merge(video_model, load=False)
      video_model.processing_error = True     
      video_model.processed_at = datetime.now(timezone.utc)
      
      await session.commit()
      

async def _assign_topics(session: AsyncSession, summary: VideoSummary, video: Video) -> list[AssignedTopic]:
  topic_repo = TopicRepository(session)
  
  topics: list[AssignedTopic] = []
  
  for t in summary.topics:
    topic = await topic_repo.get_topic(t.id) if t.id else None
    if not topic:
      topic = await topic_repo.create_topic(t.name)
    
    await topic_repo.assign_topic(topic.id, video.id, t.confidence)
    topics.append({
      "topic_id": topic.id,
      "is_new": not t.id,
      "name": t.name,
      "confidence": t.confidence
    })
    
  return topics


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
      kind=AnnotationKind.label,
      value=summary.label
    )
  )
  
  annotations.append(
    prepare_annotation(
      kind=AnnotationKind.synopsis,
      value=summary.synopsis
    )
  )
      
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
      prepare_meta(MetaSource.topic, topic.name)
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


class VideoSeriesResult(TypedDict):
  new_topics: list[str]
  existing_topics: list[str]


class VideoSeriesProcessor:
  
  def __init__(self, agent: VideoSeriesAgent, session_maker: async_sessionmaker[AsyncSession]):
    self._agent = agent
    self._db = session_maker
    
  # async def run(self, video_loader: VideoDataLoader, topic_loader: TopicLoader) -> VideoSeriesResult:
  #   async with self._db() as session:
  #     video_repo = VideoRepository(session)
  #     topic_repo = TopicRepository(session)
      
  #     video_data = await video_loader.load(video_repo)
  #     topics = await topic_loader.load(topic_repo)
    
  #   topic_decisions = await self._agent.run(video_data, topics)
    
  #   async with self._db() as session:
  #     topic_repo = TopicRepository(session)
      
  #     new_topics: list[Topic] = []
  #     existing_topics: list[Topic] = []
      
  #     for t in topic_decisions.topics:
  #       if t.decision == "new":
  #         new_topic = await topic_repo.create_topic(t.proposed_topic_name or t.canonical_topic)
  #         new_topics.append(new_topic)  
  #       elif t.decision == "existing" and t.topic_id:
  #         existing_topic = await topic_repo.get_topic(t.topic_id)
  #         if existing_topic is not None:
  #           existing_topics.append(existing_topic)
          
  #     await session.commit()
    
  #   return {
  #     "existing_topics": [t.canonical_topic for t in topic_decisions.topics if t.decision == 'existing'],
  #     "new_topics": [t.canonical_topic for t in topic_decisions.topics if t.decision == 'new']
  #   }  
      