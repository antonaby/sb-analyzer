from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun, ChallengeGenAgentResponse
from core.processors.common import JobProcessor
from db.models import Challenge
from db.repositories.challenges import ChallengeRepository
from db.repositories.helpers import full_video_data, TextVideoData
from db.repositories.jobs import CHALLENGE_GEN_JOB_NAME, ChallengeGenJob
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
      job_meta = ChallengeGenJob(**job.meta)
      video_data = await self._get_video_data(job_meta)

      run_input = ChallengeGenAgentRun(video=video_data, pattern_group_id=job_meta.pattern_group_id)
      agent_response = await self._challenge_agent.run(run_input)

      result = await self._save_challenges(job_meta, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_video_data(self, job_meta: ChallengeGenJob) -> TextVideoData:

    async with self._db() as session:
      video_repo = VideoRepository(session)
      video = await video_repo.get_video_by_id(
        job_meta.video_id,
        with_meta=True, with_annotations=True
      )

      video_data = full_video_data(video)
      return video_data

  async def _save_challenges(self, job_meta: ChallengeGenJob, agent_response: ChallengeGenAgentResponse) -> ChallengeProcessorResult:
    total_challenges: list[Challenge] = []
    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      await challenge_repo.unassign_videos(job_meta.pattern_group_id, job_meta.video_id)

      for c in agent_response.new:
        challenge_model = await challenge_repo.create_challenge(
          group_id=job_meta.pattern_group_id, name=c.name, pattern_used=c.pattern
        )
        total_challenges.append(challenge_model)

      for c in agent_response.existing:
        challenge_model = await challenge_repo.get_challenge(c.id) if c.id is not None else None
        if challenge_model is not None:
          total_challenges.append(challenge_model)

      for c in total_challenges:
        await challenge_repo.add_video(c.id, job_meta.video_id)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=[CreatedChallenge(id=c.id, name=c.name) for c in total_challenges]
    )
