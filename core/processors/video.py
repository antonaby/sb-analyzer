import logging
from datetime import datetime, timezone
from uuid import UUID

from openai import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent, VideoSummary
from core.agents.topic import TopicAgent, MainTopic
from core.file import AudioFile, UrlVideoSource, VideoFile, VideoSource
from core.processors.common import JobProcessor, PostDetails
from core.transcribe import FileAudioData, LemonfoxClient, Transcription
from core.video import ClipTaggerClient, FileVideoData, Frame
from db.models import Video, VideoAnnotation, AnnotationKind, VideoMeta, MetaSource
from db.repositories.helpers import full_video_data
from db.repositories.jobs import PROCESS_VIDEO_JOB_NAME, ProcessVideoJob, CATEGORIZATION_VIDEO_JOB_NAME, \
  CategorizationVideoJob
from db.repositories.topics import TopicRepository
from db.repositories.videos import prepare_meta, prepare_annotation, VideoRepository


class VideoProcessorError(Exception):
  pass


class BaseVideoProcessor(JobProcessor):

  def __init__(self, async_session: async_sessionmaker[AsyncSession]):
    super().__init__(async_session)

  async def _find_video(
      self,
      video_id: UUID,
      with_scraped_data: bool = False,
      with_annotations: bool = False,
      with_meta: bool = False
  ) -> Video:
    async with self._db() as session:
      repo = VideoRepository(session)
      video = await repo.get_video_by_id(
        video_id,
        with_scraped_data=with_scraped_data,
        with_annotations=with_annotations,
        with_meta=with_meta
      )
      if not video:
        raise VideoProcessorError(f"Video {video_id} not found")

      return video


class ProcessedVideo(BaseModel):
  video_id: UUID


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
    
  async def run(self, job_id: UUID) -> ProcessedVideo:
    job = await self.start_job(job_id, PROCESS_VIDEO_JOB_NAME)

    video_file: VideoFile | None = None
    video_source: VideoSource | None  = None
    job_meta: ProcessVideoJob | None = None

    try:
      job_meta = ProcessVideoJob(**job.meta)
      video = await self._find_video(job_meta.video_id, with_scraped_data=True)

      if len(video.scraped_data) == 0:
        raise VideoProcessorError(f"Video {job_meta.video_id} has no scraped data")

      last_scraped_data = max(video.scraped_data, key=lambda d: d.created_at)
      post_data = PostDetails(**last_scraped_data.data)
      video_source = await UrlVideoSource.new(post_data.download_url, self._tmp_dir)

      audio_file = AudioFile(video_source)
      video_file = VideoFile(video_source)

      audio_data = FileAudioData(self._lm_client, audio_file)
      video_data = FileVideoData(self._ct_client, video_file)
      
      summary = await self._agent.run(post_data, video_data, audio_data)

      video = await self._save_video_details(video, post_data, video_data, audio_data, summary)
      await self.set_job_finished(job_id, False)

      return ProcessedVideo(video_id=video.id)
    except Exception as e:
      if job_meta:
        await self._set_processing_error(job_meta.video_id)

      await self.set_job_finished(job_id, True)
      raise e
    finally:
      try:
        if video_file is not None:
          video_file.close()
        if video_source and job_meta and job_meta.delete_downloaded_files:
          video_source.delete()
      except Exception as e:
        self._log.exception(e)

  async def _set_processing_error(self, video_id: UUID):
    async with self._db() as session:
      video_repo = VideoRepository(session)
      await video_repo.set_video_processing(video_id, True)
      await session.commit()
        
  async def _save_video_details(
      self,
      video_model: Video,
      post_data: PostDetails, video_data: FileVideoData,
      audio_data: FileAudioData, summary: VideoSummary
  ) -> Video:

    processed_frames = await video_data.get_processed_frames()
    transcriptions = audio_data.get_processed_transcriptions()
    
    annotations, video_meta = self._create_video_data(
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

      for annotation in annotations:
        annotation.video_id = video_model.id
        annotation.revision = revision
      session.add_all(annotations)
        
      for meta in video_meta:
        meta.video_id = video_model.id
        meta.revision = revision
      session.add_all(video_meta)

      await session.commit()
      
      return video_model
      
  @classmethod
  def _create_video_data(
      cls,
      post: PostDetails, summary: VideoSummary,
      frames: list[Frame], transcriptions: list[Transcription]
  ) -> tuple[list[VideoAnnotation], list[VideoMeta]]:
    annotations: list[VideoAnnotation] = cls._create_summary_annotations(summary)
    video_meta: list[VideoMeta] = cls._create_summary_meta(summary)

    annotations.extend(
      cls._create_transcribe_annotations(transcriptions)
    )

    for frame in frames:
      annotations.extend(cls._create_frame_annotations(frame))
      video_meta.extend(cls._create_frame_video_meta(frame))

    video_meta.extend(cls._create_post_meta(post))

    return annotations, video_meta

  @classmethod
  def _create_summary_annotations(cls, summary: VideoSummary) -> list[VideoAnnotation]:
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

  @classmethod
  def _create_summary_meta(cls, summary: VideoSummary) -> list[VideoMeta]:
    video_meta: list[VideoMeta] = []

    for topic in summary.topics:
      video_meta.append(
        prepare_meta(MetaSource.topic, topic)
      )

    return video_meta

  @classmethod
  def _create_transcribe_annotations(cls, transcriptions: list[Transcription]) -> list[VideoAnnotation]:
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

  @classmethod
  def _create_post_meta(cls, post: PostDetails) -> list[VideoMeta]:
    video_meta: list[VideoMeta] = []

    if post.title:
      video_meta.append(
        prepare_meta(MetaSource.title, post.title)
      )

    if post.description:
      video_meta.append(
        prepare_meta(MetaSource.title, post.description)
      )

    for hash_tag in post.hashtags:
      video_meta.append(
        prepare_meta(MetaSource.hashtag, hash_tag)
      )

    return video_meta

  @classmethod
  def _create_frame_video_meta(cls, frame: Frame) -> list[VideoMeta]:
    video_meta: list[VideoMeta] = []

    meta_data = cls._get_frame_meta(frame)

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

  @classmethod
  def _create_frame_annotations(cls, frame: Frame) -> list[VideoAnnotation]:
    annotations: list[VideoAnnotation] = []

    cls._append_frame_ann(annotations, AnnotationKind.frame, frame.description, frame)
    cls._append_frame_ann(annotations, AnnotationKind.frame_environment, frame.environment, frame)
    cls._append_frame_ann(annotations, AnnotationKind.frame_summary, frame.summary, frame)

    for frame_object in frame.objects:
      cls._append_frame_ann(annotations, AnnotationKind.frame_object, frame_object, frame)

    for action in frame.actions:
      cls._append_frame_ann(annotations, AnnotationKind.frame_action, action, frame)

    for logo in frame.logos:
      cls._append_frame_ann(annotations, AnnotationKind.frame_logo, logo, frame)

    return annotations

  @classmethod
  def _append_frame_ann(cls, annotations: list[VideoAnnotation], kind: AnnotationKind, value: str, frame: Frame):
    annotations.append(prepare_annotation(
      kind=kind,
      value=value,
      meta=cls._get_frame_meta(frame)
    ))

  @classmethod
  def _get_frame_meta(cls, frame: Frame) -> dict:
    return {
      "frame_number": frame.frame_number,
      "time_sec": frame.time_sec
    }


class AssignedTopic(BaseModel):
  topic_id: UUID
  is_new: bool
  name: str
  confidence: float


class TopicProcessorResult(BaseModel):
  video_id: UUID
  topics: list[AssignedTopic]


class TopicProcessor(BaseVideoProcessor):

  def __init__(self, topic_agent: TopicAgent, async_session: async_sessionmaker[AsyncSession]):
    super().__init__(async_session)
    self._topic_agent = topic_agent

  async def run(self, job_id: UUID) -> TopicProcessorResult:
    job = await self.start_job(job_id, CATEGORIZATION_VIDEO_JOB_NAME)
    job_meta: CategorizationVideoJob | None = None
    try:
      job_meta = CategorizationVideoJob(**job.meta)
      video = await self._find_video(job_meta.video_id, with_scraped_data=True, with_annotations=True, with_meta=True)

      if not video.processed_at or video.processing_error:
        raise VideoProcessorError(f"Video {job_meta.video_id} unprocessed")

      video_data = full_video_data(video)
      topics = await self._topic_agent.run(video_data)

      result = await self._save_topics(video, topics)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      if job_meta:
        await self._set_categorization_error(job_meta.video_id)

      await self.set_job_finished(job_id, True)
      raise e

  async def _set_categorization_error(self, video_id: UUID):
    async with self._db() as session:
      video_repo = VideoRepository(session)
      await video_repo.set_video_categorization(video_id, True)
      await session.commit()

  async def _save_topics(self, video: Video, topics: list[MainTopic]) -> TopicProcessorResult:
    async with self._db() as session:
      video = await session.merge(video, load=False)
      video.categorization_error = False
      video.categorized_at = datetime.now(timezone.utc)

      topic_repo = TopicRepository(session)
      await topic_repo.unassign_all_topics(video.id)

      assigned_topics: list[AssignedTopic] = []
      for t in topics:
        topic = await topic_repo.get_topic(t.id) if t.id else None
        if not topic:
          topic = await topic_repo.create_topic(t.name)

        await topic_repo.assign_topic(topic.id, video.id, t.confidence)
        assigned_topics.append(
          AssignedTopic(topic_id=topic.id, is_new=t.is_new, name=t.name, confidence=t.confidence)
        )

      await session.commit()
      return TopicProcessorResult(video_id=video.id, topics=assigned_topics)
