from typing import TypedDict, cast
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient
from core.agents.video import ClipTaggerClient, VideoData
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import VideoAnnotation, VideoSource, AnnotationKind, VideoMeta, MetaSource
from db.repositories.videos import prepare_video, prepare_scraped_data, prepare_meta, prepare_annotation
from models.common import PostDetails, VideoSummary


class VideoProcessor:
  
  def __init__(
    self, 
    ct_client: ClipTaggerClient, 
    lm_client: LemonfoxClient, 
    agent: SummaryAgent, 
    async_session: async_sessionmaker[AsyncSession],
    tmp_dir: str
  ):
    self._ct_client = ct_client
    self._lm_client = lm_client
    self._agent = agent
    self._async_session = async_session
    self._tmp_dir = tmp_dir
    
  async def run(self, post: PostDetails, delete_video: bool = True) -> bool:
    source = await UrlVideoSource.new(post['download_url'], self._tmp_dir)
    video = VideoFile(source)  
    audio = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video)
    audio_data = AudioData(self._lm_client, audio)
    
    summary = await self._agent.summary(post, video_data, audio_data)
    
    async with self._async_session() as session:
      await self._save_video(post, video_data, summary, session)
      await session.commit()
    
    # TODO: release files before
    if delete_video:
      source.delete()
    
    return True
  
  async def _save_video(
    self, 
    post: PostDetails, video: VideoData, summary: VideoSummary, 
    session: AsyncSession
  ):
    processed_frames = await video.get_processed_frames()
    
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
      
    for frame in processed_frames:
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
        "duration": video.get_duration(),
        "frames": video.get_total_frames()
      },
      annotations=annotations,
      video_meta=video_meta
    )
    
    session.add(video_model)
