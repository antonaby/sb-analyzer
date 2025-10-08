from celery import Celery
import os

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_BACKEND_URL = os.getenv("CELERY_BACKEND_URL")

worker_app = Celery(
  "video-analyzer",
  broker=CELERY_BROKER_URL,
  backend=CELERY_BACKEND_URL
)

worker_app.conf.imports = ("worker.tasks")
