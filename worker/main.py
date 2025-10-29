import os

import logfire
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init, beat_init
from dotenv import load_dotenv
from utils.common import var_or_exception, enable_logfire

load_dotenv()
CELERY_BROKER_URL = var_or_exception("CELERY_BROKER_URL")
CELERY_BACKEND_URL = var_or_exception("CELERY_BACKEND_URL")


@worker_init.connect()
def init_worker(*args, **kwargs):
  if enable_logfire():
    logfire.configure(service_name="worker")
    logfire.instrument_celery()
    logfire.instrument_pydantic_ai()


@beat_init.connect()
def init_beat(*args, **kwargs):
  if enable_logfire():
    logfire.configure(service_name="beat")
    logfire.instrument_celery()


worker_app = Celery(
  "video-analyzer",
  broker=CELERY_BROKER_URL,
  backend=CELERY_BACKEND_URL
)

worker_app.conf.result_backend_transport_options = {
  'global_keyprefix': 'sb-analyzer:'
}

scraper_job_cron = os.getenv("SCAPER_JOB_CRON", "* 4 * * *")

worker_app.conf.timezone = 'UTC'
worker_app.conf.imports = ["worker.tasks"]
worker_app.conf.beat_schedule = {
  'run_scrapers': {
    'task': 'worker.tasks.scrapers.run_scrapers',
    'schedule': crontab.from_string(scraper_job_cron),
  },
}
