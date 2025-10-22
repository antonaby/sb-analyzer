import asyncio

from dotenv import load_dotenv

from apify.client import ApifyClient
from core.agents.challenge import ChallengeGenAgent
from core.agents.common import TemplateManager, gpt_5_nano, medium_effort_gpt_5, gemini_2_5_flash_lite
from core.agents.translation import TranslationAgent
from core.processors.challenge import ChallengeProcessor, TranslationProcessor
from core.processors.scraper import ApidojoScrapperProcessor, PostDetailsProcessor
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

# Agents Common
template_manager = TemplateManager()

# Agents
challenge_agent = ChallengeGenAgent(gpt_5_nano(), medium_effort_gpt_5(), template_manager)
translation_agent = TranslationAgent(gemini_2_5_flash_lite(), template_manager)

#Processors
apidojo_processor = ApidojoScrapperProcessor(apify_client, async_db)
challenge_processor = ChallengeProcessor(challenge_agent, async_db)
translation_processor = TranslationProcessor(translation_agent, async_db)
post_detail_processor = PostDetailsProcessor(async_db)
