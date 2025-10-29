import os

import logfire
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init, beat_init
from dotenv import load_dotenv

load_dotenv()
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_BACKEND_URL = os.getenv("CELERY_BACKEND_URL")

@worker_init.connect()
def init_worker(*args, **kwargs):
  logfire.configure(service_name="worker")
  logfire.instrument_celery()
  logfire.instrument_pydantic_ai()


@beat_init.connect()
def init_beat(*args, **kwargs):
  logfire.configure(service_name="beat")
  logfire.instrument_celery()
  logfire.instrument_pydantic_ai()


worker_app = Celery(
  "video-analyzer",
  broker=CELERY_BROKER_URL,
  backend=CELERY_BACKEND_URL
)

worker_app.conf.result_backend_transport_options = {
  'global_keyprefix': 'sb-analyzer:'
}

worker_app.conf.timezone = 'UTC'
worker_app.conf.imports = ["worker.tasks"]
worker_app.conf.beat_schedule = {
  'run_scrapers': {
    'task': 'worker.tasks.scrapers.run_scrapers',
    'schedule': crontab(hour=4, minute=0),
  },
}
