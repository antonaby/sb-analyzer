from typing import TypedDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient
from core.agents.video import ClipTaggerClient, VideoData
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import VideoAnnotation, VideoSource, AnnotationKind
from db.repositories.videos import prepare_video, prepare_annotation
from models.common import PostDetails, VideoSummary


class ProcessorRun(TypedDict):
  processed_frames: int


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
    
  async def run(self, post: PostDetails, delete_video: bool = True) -> ProcessorRun:
    source = await UrlVideoSource.new(post['download_url'], self._tmp_dir)
    video = VideoFile(source)  
    audio = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video)
    audio_data = AudioData(self._lm_client, audio)
    
    summary = await self._agent.summary(post, video_data, audio_data)
    
    processed_frames = await video_data.get_processed_frames()
    async with self._async_session() as session:
      await self._save_summary(post, video, summary, session)
      await session.commit()
    
    if delete_video:
      source.delete()
    
    return {
      "processed_frames": len(processed_frames)
    }
  
  async def _save_summary(
    self, 
    post: PostDetails, video: VideoFile, summary: VideoSummary, 
    session: AsyncSession
  ):
    annotations: list[VideoAnnotation] = []
    
    annotations.append(
      prepare_annotation(
        kind=AnnotationKind.SUMMARY,
        value=summary.main_idea,
        meta={
          "themes": summary.theme,
          "video_type": summary.video_type
        }
      )
    )
      
    for synopsis in summary.synopsis:
      annotations.append(
        prepare_annotation(
          kind=AnnotationKind.SUMMARY_SYNOPSIS,
          value=synopsis
        )
      )
    
    source = VideoSource(post['post_from'])
    duration =  int(video.get_duration())
    video_model = prepare_video(
      post['url'],
      post['download_url'],
      source, 
      post['title'], 
      post['author'], 
      duration,
      post['meta'],
      annotations
    )
    
    session.add(video_model)
