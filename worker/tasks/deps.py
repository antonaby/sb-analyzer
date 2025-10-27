import asyncio

from dotenv import load_dotenv

from apify.client import ApifyClient
from core.agents.challenge import ChallengeGenAgent, ChallengeLoader
from core.agents.common import TemplateManager, gpt_5_nano, medium_effort_gpt_5, gemini_2_5_flash_lite
from core.agents.summary import SummaryAgent
from core.agents.topic import TopicAgent
from core.agents.translation import TranslationAgent
from core.processors.challenge import ChallengeProcessor
from core.processors.translations import ChallengeTranslationProcessor, TopicTranslationProcessor
from core.processors.scraper import ApidojoScrapperProcessor, ApidojoPostProcessor
from core.processors.video import VideoProcessor, TopicProcessor
from core.transcribe import LemonfoxClient
from core.video import ClipTaggerClient
from db.conf import create_db_engine, get_async_session

# Env
load_dotenv()

# Async IO
loop = asyncio.new_event_loop()

# Async DB
engine = create_db_engine()
async_db = get_async_session(engine)

# Clients
apify_client = ApifyClient()
clip_tagger_client = ClipTaggerClient()
lemonfox_client = LemonfoxClient()

# Agents Common
challenge_loader = ChallengeLoader(async_db)
template_manager = TemplateManager()

# Agents
challenge_agent = ChallengeGenAgent(gpt_5_nano(), medium_effort_gpt_5(), challenge_loader, template_manager)
translation_agent = TranslationAgent(gemini_2_5_flash_lite(), template_manager)
summary_agent = SummaryAgent(gpt_5_nano(), template_manager)
topic_agent = TopicAgent(gpt_5_nano(), medium_effort_gpt_5(), template_manager)

#Processors
apidojo_processor = ApidojoScrapperProcessor(apify_client, async_db)
apidojo_post_processor = ApidojoPostProcessor(apify_client, async_db)
challenge_processor = ChallengeProcessor(challenge_agent, async_db)
challenge_translation_processor = ChallengeTranslationProcessor(translation_agent, async_db)
topic_translation_processor = TopicTranslationProcessor(translation_agent, async_db)
video_processor = VideoProcessor(clip_tagger_client, lemonfox_client, summary_agent, async_db, "./videos")
topic_processor = TopicProcessor(topic_agent, async_db)
