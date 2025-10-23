from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun, ChallengeGenAgentResponse
from core.processors.common import JobProcessor
from db.models import AnnotationKind, Challenge, Topic, Job
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import full_video_data, TextVideoData
from db.repositories.jobs import CHALLENGE_GEN_JOB_NAME, ChallengeGenJob
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository


class CreatedChallenge(BaseModel):
  id: UUID
  name: str


class ChallengeProcessorResult(BaseModel):
  challenges: list[CreatedChallenge]


class ChallengeProcessorError(Exception):
  pass


class ChallengeProcessor(JobProcessor):

  def __init__(self, challenge_agent: ChallengeGenAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._challenge_agent = challenge_agent

  async def run(self, job_id: UUID) -> ChallengeProcessorResult:
    job = await self.start_job(job_id, CHALLENGE_GEN_JOB_NAME)
    try:
      topic, video_data = await self._get_video_data(job)

      run_input = ChallengeGenAgentRun(topic=topic.name, videos=video_data, languages=["en"])
      agent_response = await self._challenge_agent.run(run_input)

      result = await self._save_challenges(topic, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_video_data(self, job: Job) -> tuple[Topic, list[TextVideoData]]:
    job_meta = ChallengeGenJob(**job.meta)
    async with self._db() as session:
      topic_repo = TopicRepository(session)
      video_repo = VideoRepository(session)

      topic = await topic_repo.get_topic(job_meta.topic_id)
      if not topic:
        raise ChallengeProcessorError(f"Topic {job_meta.topic_id} not found")

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
        raise ChallengeProcessorError(f"No videos for topic {job_meta.topic_id}")

      video_data = [full_video_data(v) for v in videos]
      return topic, video_data

  async def _save_challenges(self, topic: Topic, agent_response: ChallengeGenAgentResponse) -> ChallengeProcessorResult:
    new_challenges: list[Challenge] = []
    async with self._db() as session:
      topic = await session.merge(topic, load=False)
      topic.last_challenges_created_at = datetime.now(timezone.utc)

      challenge_repo = ChallengeRepository(session)
      for c in agent_response.challenges:
        en_translation = [t for t in c.translations if t.lang == "en"][0]
        challenge_model = await challenge_repo.create_challenge(topic.id, en_translation.name)
        new_challenges.append(challenge_model)
        await challenge_repo.create_translation(challenge_model.id, en_translation.lang, en_translation.name)

        for video in c.videos:
          await challenge_repo.add_video(challenge_model.id, video.id)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=[CreatedChallenge(id=c.id, name=c.name) for c in new_challenges]
    )
