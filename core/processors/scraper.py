from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.common import AuthorDetails, PostDetails
from db.repositories.videos import VideoRepository, prepare_scraped_data
from db.repositories.topics import TopicRepository
from db.models import VideoSource


class TopicErrorProcessor(Exception):
  pass


class NewSerachResult(TypedDict):
  serach_id: UUID


class TopicProcessor:
  
  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker
    
  async def new_search(self, topic_id: UUID, kind: str, search_data: dict) -> NewSerachResult:
    async with self._db() as session:
      topic_repo = TopicRepository(session)  
      topic = await topic_repo.get_topic(topic_id)
      if topic is None:
        raise TopicErrorProcessor(f"Topic not found, id={topic_id}")
      
      search = await topic_repo.create_serach(topic, kind, search_data)
      await session.commit()
      
    return {
      "serach_id": search.id
    }
  
  
    

class Result(TypedDict):
  author_id: UUID
  new_author: bool
  video_id: UUID
  new_video: bool


class ScraperProcessor:
  
  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker
    
  async def run(self, author: AuthorDetails, post: PostDetails) -> Result:
    async with self._db() as session:
      repo = VideoRepository(session)
      
      author_source = VideoSource(author['author_from'])
      author_model, is_author_new = await repo.upsert_author(
        author['url'], 
        author_source, 
        author['verified'], 
        author['followers'], 
        author['total_videos']
      )
      
      video_source = VideoSource(post['post_from'])
      uploaded_at = datetime.fromisoformat(post["uploaded_at_iso"])
      
      video_model, is_video_new = await repo.upsert_video(
        post['url'], 
        video_source, 
        author_model, 
        uploaded_at, 
        post["likes"], 
        post["views"], 
        post["comments"]
      )
      video_model.scraped_data = prepare_scraped_data(cast(dict, post))
      
      await session.commit()
      
      return {
        "author_id": author_model.id,
        "new_author": is_author_new,
        "video_id": video_model.id,
        "new_video": is_video_new
      }
