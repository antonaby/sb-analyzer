from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.translation import TranslationAgent, TranslationAgentRun, Translation, TranslationAgentResponse
from core.processors.common import JobProcessor, CreatedTranslation
from db.models import Job, Challenge, ChallengeTranslation
from db.repositories.challenges import ChallengeRepository
from db.repositories.jobs import CHALLENGE_TRANSLATION_JOB_NAME, TranslationJob


class TranslationProcessorError(Exception):
  pass


class TranslationProcessorResult(BaseModel):
  translations: list[CreatedTranslation]


class ChallengeTranslationProcessor(JobProcessor):

  def __init__(self, translation_agent: TranslationAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._translation_agent = translation_agent

  async def run(self, job_id: UUID) -> TranslationProcessorResult:
    job = await self.start_job(job_id, CHALLENGE_TRANSLATION_JOB_NAME)
    try:
      challenge, translations_to_create = await self._get_translation(job)
      if len(translations_to_create) == 0:
        await self.set_job_finished(job_id, False)
        return TranslationProcessorResult(translations=[])

      agent_response = await self._translation_agent.run(TranslationAgentRun(
        languages=translations_to_create,
        input=Translation(lang="en", text=challenge.name)
      ))

      result = await self._save_translations(challenge, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_translation(self, job: Job) -> tuple[Challenge, list[str]]:
    job_meta = TranslationJob(**job.meta)

    translations_to_create: list[str] = job_meta.langs

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(job_meta.target_id, with_translations=True)
      if not challenge:
        raise TranslationProcessorError(f"Challenge {job_meta.target_id} not found")

      for c in challenge.translations:
        if c.lang in translations_to_create:
          translations_to_create.remove(c.lang)

    return challenge, translations_to_create

  async def _save_translations(
      self,
      challenge: Challenge,
      agent_response: TranslationAgentResponse
  ) -> TranslationProcessorResult:
    created_translations: list[ChallengeTranslation] = []
    async with self._db() as session:
      challenge = await session.merge(challenge, load=False)
      challenge.translated_at = datetime.now(timezone.utc)

      challenge_repo = ChallengeRepository(session)

      for t in agent_response.translations:
        t_model = await challenge_repo.create_translation(challenge.id, t.lang, t.text)
        created_translations.append(t_model)

      en_translation = next((t for t in created_translations if t.lang == "en"), None)
      if en_translation is None:
        t_model = await challenge_repo.create_translation(challenge.id, "en", challenge.name)
        created_translations.append(t_model)

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])
