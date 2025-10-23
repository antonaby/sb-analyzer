from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.translation import TranslationAgent, TranslationAgentRun, Translation, TranslationAgentResponse
from core.processors.common import JobProcessor, CreatedTranslation
from db.models import Job, Challenge, ChallengeTranslation, TopicTranslation, Topic
from db.repositories.challenges import ChallengeRepository
from db.repositories.jobs import CHALLENGE_TRANSLATION_JOB_NAME, TranslationJob, TOPIC_TRANSLATION_JOB_NAME
from db.repositories.topics import TopicRepository


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
      challenge, en_translation, translations_to_create = await self._get_translation(job)
      if len(translations_to_create) == 0:
        await self.set_job_finished(job_id, False)
        return TranslationProcessorResult(translations=[])

      agent_response = await self._translation_agent.run(TranslationAgentRun(
        languages=translations_to_create,
        input=Translation(lang=en_translation.lang, text=en_translation.value)
      ))

      result = await self._save_translations(challenge, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_translation(self, job: Job) -> tuple[Challenge, ChallengeTranslation, list[str]]:
    job_meta = TranslationJob(**job.meta)

    translations_to_create: list[str] = job_meta.langs
    en_translation: ChallengeTranslation | None = None

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(job_meta.target_id, with_translations=True)
      if not challenge:
        raise TranslationProcessorError(f"Challenge {job_meta.target_id} not found")

      for c in challenge.translations:
        if c.lang == "en":
          en_translation = c
        if c.lang in translations_to_create:
          translations_to_create.remove(c.lang)

    if not en_translation:
      raise TranslationProcessorError(f"No en translation for challenge {job_meta.target_id}")

    return challenge, en_translation, translations_to_create

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

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])


class TopicTranslationProcessor(JobProcessor):

  def __init__(self, translation_agent: TranslationAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._translation_agent = translation_agent

  async def run(self, job_id: UUID) -> TranslationProcessorResult:
    job = await self.start_job(job_id, TOPIC_TRANSLATION_JOB_NAME)
    try:
      topic, translations_to_create = await self._get_translation(job)
      if len(translations_to_create) == 0:
        await self.set_job_finished(job_id, False)
        return TranslationProcessorResult(translations=[])

      agent_response = await self._translation_agent.run(TranslationAgentRun(
        languages=translations_to_create,
        input=Translation(lang="en", text=topic.name)
      ))

      result = await self._save_translations(topic, agent_response)
      await self.set_job_finished(job_id, False)

      return result
    except Exception as e:
      await self.set_job_finished(job_id, True)
      raise e

  async def _get_translation(self, job: Job) -> tuple[Topic, list[str]]:
    job_meta = TranslationJob(**job.meta)

    translations_to_create: list[str] = job_meta.langs

    async with self._db() as session:
      topic_repo = TopicRepository(session)
      topic = await topic_repo.get_topic(job_meta.target_id, with_translations=True)
      if not topic:
        raise TranslationProcessorError(f"Topic {job_meta.target_id} not found")

      for c in topic.translations:
        if c.lang in translations_to_create:
          translations_to_create.remove(c.lang)

    return topic, translations_to_create

  async def _save_translations(
      self,
      topic: Topic,
      agent_response: TranslationAgentResponse
  ) -> TranslationProcessorResult:
    created_translations: list[TopicTranslation] = []
    async with self._db() as session:
      topic = await session.merge(topic, load=False)
      topic.translated_at = datetime.now(timezone.utc)
      topic_repo = TopicRepository(session)

      for t in agent_response.translations:
        t_model = await topic_repo.create_translation(topic.id, t.lang, t.text)
        created_translations.append(t_model)

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])
