import asyncio

from dotenv import load_dotenv

from core.agents.challenge import ChallengeGenAgent
from core.agents.common import TemplateManager, gpt_5_nano, medium_effort_gpt_5
from core.processors.challenge import ChallengeProcessor
from db.conf import create_db_engine, get_async_session

# Env
load_dotenv()

# Async IO
loop = asyncio.new_event_loop()

# Async DB
engine = create_db_engine()
async_db = get_async_session(engine)

# Agents Common
template_manager = TemplateManager()

# Agents
challenge_agent = ChallengeGenAgent(gpt_5_nano(), medium_effort_gpt_5(), template_manager)

#Processors
challenge_processor = ChallengeProcessor(challenge_agent, async_db)
