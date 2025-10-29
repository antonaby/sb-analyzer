import logfire
from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.conf import create_db_engine, get_async_session
from db.repositories.authors import AuthorRepository
from db.repositories.challenges import ChallengeRepository
from db.repositories.jobs import JobRepository
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository
from utils.common import enable_logfire

load_dotenv()
if enable_logfire():
  logfire.configure(service_name="api")

db_engine = create_db_engine()
logfire.instrument_sqlalchemy(engine=db_engine)
AsyncSessionLocal = get_async_session(db_engine)

async def get_async_db():
  async with AsyncSessionLocal() as session:
    yield session


def get_video_repo(session: AsyncSession = Depends(get_async_db)) -> VideoRepository:
  return VideoRepository(session)


def get_topic_repo(session: AsyncSession = Depends(get_async_db)) -> TopicRepository:
  return TopicRepository(session)

def get_author_repo(session: AsyncSession = Depends(get_async_db)) -> AuthorRepository:
  return AuthorRepository(session)

def get_job_repo(session: AsyncSession = Depends(get_async_db)) -> JobRepository:
  return JobRepository(session)

def get_challenge_repo(session: AsyncSession = Depends(get_async_db)) -> ChallengeRepository:
  return ChallengeRepository(session)
