import logging
from typing import TypedDict, cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient, Transcription
from core.agents.video import ClipTaggerClient, VideoData, Frame
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import Video, VideoAnnotation, VideoSource, AnnotationKind, VideoMeta, MetaSource
from db.repositories.videos import prepare_video, prepare_scraped_data, prepare_meta, prepare_annotation
from models.common import PostDetails, VideoSummary


class VideoProcessorError(Exception):
  pass


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
    self._async_session = async_session
    self._tmp_dir = tmp_dir
    
  async def run(self, post: PostDetails, delete_video: bool = True) -> dict:
    source = await UrlVideoSource.new(post['download_url'], self._tmp_dir)
    video_file = VideoFile(source)  
    audio_file = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video_file)
    audio_data = AudioData(self._lm_client, audio_file)
    
    try:
      summary = await self._agent.summary(post, video_data, audio_data)
      processed_frames = await video_data.get_processed_frames()
      video_model = _create_video(post, video_data, audio_data, summary, processed_frames)
      
      async with self._async_session() as session:
        session.add(video_model)
        await session.commit()
      
      return {
        "video_id": video_model.id
      }
    except Exception as e:
      raise VideoProcessorError("cannot create summary for a video") from e
    finally:
      try:
        video_file.close()
        if delete_video:
          source.delete()
      except Exception as e:
        self._log.exception(e)


def _create_video(
  post: PostDetails, 
  video_data: VideoData, audio_data: AudioData, 
  summary: VideoSummary, frames: list[Frame]
) -> Video:
  annotations: list[VideoAnnotation] = _create_summary_annotations(summary)
  video_meta: list[VideoMeta] = _create_summary_meta(summary)
  
  annotations.extend(
    _create_transcribe_annotations(audio_data.get_processed_transcriptions())
  )
  
  for frame in frames:
    annotations.extend(_create_frame_annotations(frame))
    video_meta.extend(_create_frame_video_meta(frame))
        
  video_meta.extend(_create_post_meta(post))
  source = VideoSource(post['post_from'])
  scraped_data = prepare_scraped_data(cast(dict, post))
  
  video_model = prepare_video(
    url=post["url"],
    source=source,
    scraped_data=scraped_data,
    extra_data={
      "duration": video_data.get_duration(),
      "frames": video_data.get_total_frames()
    },
    annotations=annotations,
    video_meta=video_meta
  )
  
  return video_model


def _create_summary_annotations(summary: VideoSummary) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  annotations.append(
    prepare_annotation(
      kind=AnnotationKind.SUMMARY,
      value=summary.main_idea
    )
  )
      
  for synopsis in summary.synopsis:
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.SUMMARY_SYNOPSIS,
        value=synopsis
      )
    )
  
  return annotations


def _create_summary_meta(summary: VideoSummary) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  for theme in summary.theme:
    video_meta.append(
      prepare_meta(MetaSource.SUMMARY, theme)
    )  
  
  for video_type in summary.video_type:
    video_meta.append(
      prepare_meta(MetaSource.SUMMARY_VIDEO_TYPE, video_type)
    ) 
  
  return video_meta


def _create_transcribe_annotations(transcriptions: list[Transcription]) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  for segment in transcriptions:
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.TRANSCRIPTION,
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
  
  video_meta.append(
    prepare_meta(MetaSource.POST_AUTHOR, post.get("author", "no author"))
  )
  video_meta.append(
    prepare_meta(MetaSource.POST, post.get("title", "no title"))
  )
  
  for hash_tag in post.get("hashtags", []):
    video_meta.append(
      prepare_meta(MetaSource.HASHTAG, hash_tag)
    )
  
  return video_meta


def _create_frame_video_meta(frame: Frame) -> list[VideoMeta]:
  video_meta: list[VideoMeta] = []
  
  video_meta.append(
    prepare_meta(MetaSource.FRAME_CONTENT_TYPE, frame.content_type)
  )
  video_meta.append(
    prepare_meta(MetaSource.FRAME_STYLE, frame.specific_style)
  )
  video_meta.append(
    prepare_meta(MetaSource.FRAME_QUALITY, frame.production_quality)
  )
  
  return video_meta
  

def _create_frame_annotations(frame: Frame) -> list[VideoAnnotation]:
  annotations: list[VideoAnnotation] = []
  
  _append_frame(annotations, AnnotationKind.FRAME, frame.description, frame)
  _append_frame(annotations, AnnotationKind.FRAME_ENVIRONMENT, frame.environment, frame)
  _append_frame(annotations, AnnotationKind.FRAME_SUMMARY, frame.summary, frame)
  _append_frame(annotations, AnnotationKind.FRAME, frame.description, frame)
  
  for object in frame.objects:
    _append_frame(annotations, AnnotationKind.FRAME_OBJECT, object, frame)

  for action in frame.actions:
    _append_frame(annotations, AnnotationKind.FRAME_ACTION, action, frame)

  for logo in frame.logos:
    _append_frame(annotations, AnnotationKind.FRAME_LOGO, logo, frame)
  
  return annotations


def _append_frame(annotations: list[VideoAnnotation], kind: AnnotationKind, value: str, frame: Frame):
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
