from datetime import timezone, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun, ChallengeGenAgentResponse, \
  ChallengeCategoryAgent, ChallengeCategoryAgentRun, ChallengeCategoryAgentResponse
from core.agents.common import TopicName
from core.processors.common import JobProcessor
from db.models import Video, Challenge
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import full_video_data, TextVideoData
from db.repositories.jobs import CHALLENGE_GEN_JOB_NAME, ChallengeGenJob, CHALLENGE_CATEGORIZATION_JOB_NAME, \
  ChallengeCategorizationJob
from db.repositories.topics import TopicRepository
from db.repositories.videos import VideoRepository


class ChallengeDetails(BaseModel):
  id: UUID
  name: str
  is_new: bool


class ChallengeProcessorResult(BaseModel):
  challenges: list[ChallengeDetails]


class ChallengeProcessorError(Exception):
  pass


class ChallengeProcessor(JobProcessor):

  def __init__(self, challenge_agent: ChallengeGenAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._challenge_agent = challenge_agent

  async def run(self, job_id: UUID) -> ChallengeProcessorResult:
    job = await self.start_job(job_id, CHALLENGE_GEN_JOB_NAME)
    job_meta: ChallengeGenJob | None = None
    try:
      job_meta = ChallengeGenJob(**job.meta)
      video, video_data = await self._get_video_data(job_meta)

      run_input = ChallengeGenAgentRun(video=video_data, pattern_group_id=job_meta.pattern_group_id)
      agent_response = await self._challenge_agent.run(run_input)

      result = await self._save_challenges(video, job_meta, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      if job_meta:
        await self._set_challenges_creating_error(job_meta.video_id)

      await self.set_job_finished(job_id, True)
      raise e

  async def _get_video_data(self, job_meta: ChallengeGenJob) -> tuple[Video, TextVideoData]:

    async with self._db() as session:
      video_repo = VideoRepository(session)
      video = await video_repo.get_video_by_id(
        job_meta.video_id,
        with_meta=True, with_annotations=True
      )

      video_data = full_video_data(video)
      return video, video_data

  async def _set_challenges_creating_error(self, video_id: UUID):
    async with self._db() as session:
      video_repo = VideoRepository(session)
      await video_repo.set_challenge_creating(video_id, True)
      await session.commit()

  async def _save_challenges(self, video: Video, job_meta: ChallengeGenJob, agent_response: ChallengeGenAgentResponse) -> ChallengeProcessorResult:
    total_challenges: list[ChallengeDetails] = []
    async with self._db() as session:
      video = await session.merge(video, load=False)
      video.challenges_created_at = datetime.now(timezone.utc)
      video.challenges_creating_error = False

      challenge_repo = ChallengeRepository(session)
      await challenge_repo.unassign_videos(job_meta.pattern_group_id, job_meta.video_id)

      for c in agent_response.new:
        challenge_model = await challenge_repo.create_challenge(
          group_id=job_meta.pattern_group_id, name=c.name, pattern_used=c.pattern
        )
        total_challenges.append(
          ChallengeDetails(id=challenge_model.id, name=challenge_model.name, is_new=True)
        )

      for c in agent_response.existing:
        challenge_model = await challenge_repo.get_challenge(c.id) if c.id is not None else None
        if challenge_model is not None:
          total_challenges.append(
            ChallengeDetails(id=challenge_model.id, name=challenge_model.name, is_new=False)
          )

      for c in total_challenges:
        await challenge_repo.add_video(c.id, job_meta.video_id)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=total_challenges
    )


class ChallengeCategoryProcessor(JobProcessor):

  def __init__(self, challenge_cat_agent: ChallengeCategoryAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._agent = challenge_cat_agent

  async def run(self, job_id: UUID):
    job = await self.start_job(job_id, CHALLENGE_CATEGORIZATION_JOB_NAME)
    job_meta: ChallengeCategorizationJob | None = None

    try:
      job_meta = ChallengeCategorizationJob(**job.meta)
      challenge, topics = await self._get_challenge(job_meta)

      run_input = ChallengeCategoryAgentRun(challenge=challenge.name, topics=topics)
      agent_response = await self._agent.run(run_input)

      result = await self._save_categories(job_meta, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      if job_meta:
        await self._set_challenges_categorization_error(job_meta.challenge_id)

      await self.set_job_finished(job_id, True)
      raise e

  async def _set_challenges_categorization_error(self, challenge_id: UUID):
    pass

  async def _get_challenge(self, job_meta: ChallengeCategorizationJob) -> tuple[Challenge, list[TopicName]]:
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(job_meta.challenge_id, with_translations=False)
      if not challenge:
        raise ChallengeProcessorError(f"Challenge {job_meta.challenge_id} not found")

      topic_repo = TopicRepository(session)
      all_topics = await topic_repo.get_all_topics()
      topic_names = [TopicName(id=t.id, name=t.name) for t in all_topics]

      return challenge, topic_names

  async def _save_categories(self,
                             job_meta: ChallengeCategorizationJob,
                             agent_response: ChallengeCategoryAgentResponse):
    pass
