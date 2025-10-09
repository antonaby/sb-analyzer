import logging
from typing import TypedDict, cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient
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
      video_model = self._create_video(post, video_data, audio_data, summary, processed_frames)
      
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
    self, 
    post: PostDetails, 
    video_data: VideoData, audio_data: AudioData, 
    summary: VideoSummary, 
    frames: list[Frame]
  ) -> Video:
    annotations: list[VideoAnnotation] = []
    video_meta: list[VideoMeta] = []
    
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
      
    for segment in audio_data.get_processed_transcriptions():
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
      
    for frame in frames:
      annotations.append(
        prepare_annotation(
          kind=AnnotationKind.FRAME,
          value=frame.description,
          meta={
            "frame_number": frame.frame_number,
            "time_sec": frame.time_sec
          }
        )
      )
      annotations.append(
        prepare_annotation(
          kind=AnnotationKind.FRAME_ENVIRONMENT,
          value=frame.environment,
          meta={
            "frame_number": frame.frame_number,
            "time_sec": frame.time_sec
          }
        )
      )
      annotations.append(
        prepare_annotation(
          kind=AnnotationKind.FRAME_SUMMARY,
          value=frame.summary,
          meta={
            "frame_number": frame.frame_number,
            "time_sec": frame.time_sec
          }
        )
      )
      for object in frame.objects:
        annotations.append(
          prepare_annotation(
            kind=AnnotationKind.FRAME_OBJECT,
            value=object,
            meta={
              "frame_number": frame.frame_number,
              "time_sec": frame.time_sec
            }
          )
        )
      for action in frame.actions:
        annotations.append(
          prepare_annotation(
            kind=AnnotationKind.FRAME_ACTION,
            value=action,
            meta={
              "frame_number": frame.frame_number,
              "time_sec": frame.time_sec
            }
          )
        )
      for logo in frame.logos:
        annotations.append(
          prepare_annotation(
            kind=AnnotationKind.FRAME_LOGO,
            value=logo,
            meta={
              "frame_number": frame.frame_number,
              "time_sec": frame.time_sec
            }
          )
        )
      video_meta.append(
        prepare_meta(MetaSource.FRAME_CONTENT_TYPE, frame.content_type)
      )
      video_meta.append(
        prepare_meta(MetaSource.FRAME_STYLE, frame.specific_style)
      )
      video_meta.append(
        prepare_meta(MetaSource.FRAME_QUALITY, frame.production_quality)
      )
    
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
    for theme in summary.theme:
      video_meta.append(
        prepare_meta(MetaSource.SUMMARY, theme)
      )  
    for video_type in summary.video_type:
      video_meta.append(
        prepare_meta(MetaSource.SUMMARY_VIDEO_TYPE, video_type)
      ) 
    
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
