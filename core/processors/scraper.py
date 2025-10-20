from datetime import datetime
from typing import TypedDict, cast
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.common import AuthorDetails, PostDetails
from db.repositories.videos import VideoRepository, prepare_scraped_data
from db.repositories.topics import TopicRepository
from db.models import VideoSource


class NewSearchResult(TypedDict):
  search_id: UUID
  created_at: datetime
  
  
class UpdateSearchResult(TypedDict):
  search_id: UUID
  ran_at: datetime | None


class SearchProcessor:
  
  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker
    
  async def new_search(self, scraper: str, kind: str, search_data: dict) -> NewSearchResult:
    async with self._db() as session:
      topic_repo = TopicRepository(session)
      
      search = await topic_repo.create_search(scraper, kind, search_data)
      await session.commit()
      
    return {
      "search_id": search.id,
      "created_at": search.created_at
    }
  
  async def update_search(self, search_id: UUID, total_videos: int) -> UpdateSearchResult:
    async with self._db() as session:
      topic_repo = TopicRepository(session)
      
      updated_search = await topic_repo.update_search(search_id, total_videos)
      await session.commit()
    
    return {
      "search_id": updated_search.id,
      "ran_at": updated_search.ran_at
    }


class SavePostResult(TypedDict):
  author_id: UUID
  new_author: bool
  video_id: UUID
  new_video: bool


class PostDetailsProcessor:
  
  def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
    self._db = session_maker
    
  async def save(self, author: AuthorDetails, post: PostDetails) -> SavePostResult:
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
      scraped_data = prepare_scraped_data(video_model.id, cast(dict, post))
      session.add(scraped_data)

      search_id = UUID(post["search_id"])
      await repo.add_search(search_id, video_model.id, is_video_new)

      for hashtag in post["hashtags"]:
        hashtag_model = await repo.upsert_hashtag(hashtag, video_source)
        await repo.assign_hashtag(video_model.id, hashtag_model.id)
      
      await session.commit()
      
      return {
        "author_id": author_model.id,
        "new_author": is_author_new,
        "video_id": video_model.id,
        "new_video": is_video_new,
      }
