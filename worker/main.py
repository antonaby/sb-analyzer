import os

import logfire
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init, beat_init
from dotenv import load_dotenv

from utils.common import var_or_exception, configure_logfire

load_dotenv()
CELERY_BROKER_URL = var_or_exception("CELERY_BROKER_URL")
CELERY_BACKEND_URL = var_or_exception("CELERY_DATABASE_URL")


@worker_init.connect()
def init_worker(*args, **kwargs):
  configure_logfire("worker")
  logfire.instrument_celery()
  logfire.instrument_pydantic_ai()


@beat_init.connect()
def init_beat(*args, **kwargs):
  configure_logfire("beat")
  logfire.instrument_celery()


worker_app = Celery(
  "video-analyzer",
  broker=CELERY_BROKER_URL,
  backend=CELERY_BACKEND_URL
)

worker_app.conf.update(
  timezone = 'UTC',
  imports = ["worker.tasks"]
)

scraper_job_cron = os.getenv("SCAPER_JOB_CRON", "* 4 * * *")

worker_app.conf.beat_schedule = {
  'run_scrapers': {
    'task': 'worker.tasks.scrapers.run_scrapers',
    'schedule': crontab.from_string(scraper_job_cron),
  },
}
