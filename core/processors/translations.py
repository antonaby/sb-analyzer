from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.translation import TranslationAgent, TranslationAgentRun, Translation, TranslationAgentResponse
from core.processors.common import JobProcessor, CreatedTranslation
from db.models import Challenge, ChallengeTranslation
from db.repositories.challenges import ChallengeRepository
from models.videos import ChallengeTranslationSpec


class TranslationProcessorError(Exception):
  pass


class TranslationProcessorResult(BaseModel):
  translations: list[CreatedTranslation]


class ChallengeTranslationProcessor(JobProcessor):

  def __init__(self, translation_agent: TranslationAgent, session_maker: async_sessionmaker[AsyncSession]):
    super().__init__(session_maker)
    self._translation_agent = translation_agent

  async def run(self, spec: ChallengeTranslationSpec) -> TranslationProcessorResult:
    challenge, translations_to_create = await self._get_translation(spec)
    if len(translations_to_create) == 0:
      return TranslationProcessorResult(translations=[])

    agent_response = await self._translation_agent.run(TranslationAgentRun(
      languages=translations_to_create,
      input=Translation(lang="en", text=challenge.name)
    ))

    result = await self._save_translations(spec, challenge, agent_response)

    return result

  async def _get_translation(self, spec: ChallengeTranslationSpec) -> tuple[Challenge, list[str]]:
    translations_to_create: list[str] = spec.langs.copy()

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(spec.challenge_id, with_translations=spec.append)
      if not challenge:
        raise TranslationProcessorError(f"Challenge {spec.challenge_id} not found")

      if spec.append:
        for c in challenge.translations:
          if c.lang in translations_to_create:
            translations_to_create.remove(c.lang)

    return challenge, translations_to_create

  async def _save_translations(
      self,
      spec: ChallengeTranslationSpec,
      challenge: Challenge,
      agent_response: TranslationAgentResponse
  ) -> TranslationProcessorResult:
    created_translations: list[ChallengeTranslation] = []
    async with self._db() as session:
      challenge = await session.merge(challenge, load=False)
      challenge.translated_at = datetime.now(timezone.utc)

      challenge_repo = ChallengeRepository(session)
      if not spec.append:
        await challenge_repo.delete_old_translations(challenge.id)

      for t in agent_response.translations:
        t_model = await challenge_repo.create_translation(challenge.id, t.lang, t.text)
        created_translations.append(t_model)

      if not spec.append:
        en_translation = next((t for t in created_translations if t.lang == "en"), None)
        if en_translation is None:
          t_model = await challenge_repo.create_translation(challenge.id, "en", challenge.name)
          created_translations.append(t_model)

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])
