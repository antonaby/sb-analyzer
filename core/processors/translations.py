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
      job_meta = TranslationJob(**job.meta)
      challenge, translations_to_create = await self._get_translation(job_meta)
      if len(translations_to_create) == 0:
        await self.set_job_finished(job_id, False)
        return TranslationProcessorResult(translations=[])

      agent_response = await self._translation_agent.run(TranslationAgentRun(
        languages=translations_to_create,
        input=Translation(lang="en", text=challenge.name)
      ))

      result = await self._save_translations(job_meta, challenge, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_translation(self, job_meta: TranslationJob) -> tuple[Challenge, list[str]]:
    translations_to_create: list[str] = job_meta.langs.copy()

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(job_meta.target_id, with_translations=job_meta.append)
      if not challenge:
        raise TranslationProcessorError(f"Challenge {job_meta.target_id} not found")

      if job_meta.append:
        for c in challenge.translations:
          if c.lang in translations_to_create:
            translations_to_create.remove(c.lang)

    return challenge, translations_to_create

  async def _save_translations(
      self,
      job_meta: TranslationJob,
      challenge: Challenge,
      agent_response: TranslationAgentResponse
  ) -> TranslationProcessorResult:
    created_translations: list[ChallengeTranslation] = []
    async with self._db() as session:
      challenge = await session.merge(challenge, load=False)
      challenge.translated_at = datetime.now(timezone.utc)

      challenge_repo = ChallengeRepository(session)
      if not job_meta.append:
        await challenge_repo.delete_old_translations(challenge.id)

      for t in agent_response.translations:
        t_model = await challenge_repo.create_translation(challenge.id, t.lang, t.text)
        created_translations.append(t_model)

      if not job_meta.append:
        en_translation = next((t for t in created_translations if t.lang == "en"), None)
        if en_translation is None:
          t_model = await challenge_repo.create_translation(challenge.id, "en", challenge.name)
          created_translations.append(t_model)

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])
