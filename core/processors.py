from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agents.summary import SummaryAgent
from core.agents.transcribe import AudioData, LemonfoxClient
from core.agents.video import ClipTaggerClient, VideoData
from core.file import AudioFile, UrlVideoSource, VideoFile
from db.models import VideoSource, AnnotationKind
from db.repositories.videos import VideoRepository
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
    
  async def run(self, post: PostDetails, delete_video: bool = True) -> VideoSummary:
    source = await UrlVideoSource.new(post['download_url'], self._tmp_dir)
    video = VideoFile(source)  
    audio = AudioFile(source)
    
    video_data = VideoData(self._ct_client, video)
    audio_data = AudioData(self._lm_client, audio)
    
    summary = await self._agent.summary(post, video_data, audio_data)
    
    if delete_video:
      source.delete()
    
    async with self._async_session() as session:
      video_repo = VideoRepository(session)
      
      source = VideoSource(post['post_from'])
      duration =  int(video.get_duration())
      video_model = await video_repo.create_video(
        post['url'],
        post['download_url'],
        source, 
        post['title'], 
        post['author'], 
        duration,
        post['meta']
      )
      
      await session.flush()
      
      await video_repo.create_annotation(
        video_model.id,
        AnnotationKind.SUMMARY,
        summary.main_idea,
      )
      
      await session.commit()
    
    return summary
