from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun
from db.models import AnnotationKind
from db.repositories.helpers import full_video_data
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository


class ChallengeProcessorError(Exception):
  pass


class ChallengeProcessor:

  def __init__(self, challenge_agent: ChallengeGenAgent, session_maker: async_sessionmaker[AsyncSession]):
    self._challenge_agent = challenge_agent
    self._db = session_maker

  async def create_challenges(self, topic_id: UUID):
    async with self._db() as session:
      topic_repo = TopicRepository(session)
      video_repo = VideoRepository(session)

      topic = await topic_repo.get_topic(topic_id)
      if not topic:
        raise ChallengeProcessorError(f"Topic {topic_id} not found")

      videos = await video_repo.get_video_by_topic(
        topic_id,
        load_annotations=True,
        annotations_to_load=[AnnotationKind.label,
                             AnnotationKind.synopsis,
                             AnnotationKind.action,
                             AnnotationKind.transcription],
        load_meta=True,
        max_videos=20
      )

      if len(videos) == 0:
        raise ChallengeProcessorError(f"No videos for topic {topic_id}")

      video_data = [full_video_data(v) for v in videos]

    run_input = ChallengeGenAgentRun(topic=topic.name, videos=video_data, languages=["en"])
    challenges = await self._challenge_agent.run(run_input)

    return challenges
