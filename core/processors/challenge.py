from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun
from db.models import AnnotationKind, Challenge
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import full_video_data
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository


class CreatedChallenge(BaseModel):
  id: UUID
  name: str


class ChallengeProcessorResult(BaseModel):
  challenges: list[CreatedChallenge]


class ChallengeProcessorError(Exception):
  pass


class ChallengeProcessor:

  def __init__(self, challenge_agent: ChallengeGenAgent, session_maker: async_sessionmaker[AsyncSession]):
    self._challenge_agent = challenge_agent
    self._db = session_maker

  async def create_challenges(self, topic_id: UUID) -> ChallengeProcessorResult:
    async with self._db() as session:
      topic_repo = TopicRepository(session)
      video_repo = VideoRepository(session)

      topic = await topic_repo.get_topic(topic_id)
      if not topic:
        raise ChallengeProcessorError(f"Topic {topic_id} not found")

      videos = await video_repo.get_video_by_topic(
        topic.id,
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
    agent_response = await self._challenge_agent.run(run_input)

    new_challenges: list[Challenge] = []

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      for c in agent_response.challenges:
        name = next((t.name for t in c.translations if t.lang == "en"), "no en name")
        challenge_model = await challenge_repo.create_challenge(topic.id, name)
        new_challenges.append(challenge_model)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=[CreatedChallenge(id=c.id, name=c.name) for c in new_challenges]
    )
