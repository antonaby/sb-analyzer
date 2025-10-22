from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.agents.challenge import ChallengeGenAgent, ChallengeGenAgentRun
from core.agents.translation import TranslationAgent, TranslationAgentRun, Translation
from db.models import AnnotationKind, Challenge, ChallengeTranslation
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
        en_translation = [t for t in c.translations if t.lang == "en"][0]
        challenge_model = await challenge_repo.create_challenge(topic.id, en_translation.name)
        new_challenges.append(challenge_model)
        await challenge_repo.create_translation(challenge_model.id, en_translation.lang, en_translation.name)

      await session.commit()

    return ChallengeProcessorResult(
      challenges=[CreatedChallenge(id=c.id, name=c.name) for c in new_challenges]
    )


class CreatedTranslation(BaseModel):
  id: UUID
  land: str
  text: str


class TranslationProcessorResult(BaseModel):
  translations: list[CreatedTranslation]


class TranslationProcessor:

  def __init__(self, translation_agent: TranslationAgent, session_maker: async_sessionmaker[AsyncSession]):
    self._translation_agent = translation_agent
    self._db = session_maker

  async def translate(self, challenge_id: UUID, langs: list[str]) -> TranslationProcessorResult:
    translations_to_create: list[str] = langs
    en_translation: ChallengeTranslation | None = None

    async with self._db() as session:
      challenge_repo = ChallengeRepository(session)
      challenge = await challenge_repo.get_challenge(challenge_id, with_translations=True)
      if not challenge:
        raise ChallengeProcessorError(f"Challenge {challenge_id} not found")

      for c in challenge.translations:
        if c.lang == "en":
          en_translation = c
        if c.lang in translations_to_create:
          translations_to_create.remove(c.lang)

    if not en_translation:
      raise ChallengeProcessorError(f"No en translation for challenge {challenge_id}")

    if len(translations_to_create) == 0:
      return TranslationProcessorResult(translations=[])

    result = await self._translation_agent.run(TranslationAgentRun(
      languages=translations_to_create,
      input=Translation(lang=en_translation.lang, text=en_translation.value)
    ))

    created_translations: list[ChallengeTranslation] = []
    async with self._db() as session:
      challenge = await session.merge(challenge, load=False)
      challenge.translated_at = datetime.now(timezone.utc)

      challenge_repo = ChallengeRepository(session)

      for t in result.translations:
        t_model = await challenge_repo.create_translation(challenge.id, t.lang, t.text)
        created_translations.append(t_model)

      await session.commit()

    return TranslationProcessorResult(translations=[
      CreatedTranslation(id=t.id, land=t.lang, text=t.value) for t in created_translations
    ])
