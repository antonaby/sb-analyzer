from celery import Celery
from dotenv import load_dotenv
import os

load_dotenv()
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
CELERY_BACKEND_URL = os.getenv("CELERY_BACKEND_URL")

worker_app = Celery(
  "video-analyzer",
  broker=CELERY_BROKER_URL,
  backend=CELERY_BACKEND_URL
)

worker_app.conf.result_backend_transport_options = {
  'global_keyprefix': 'sb-analyzer:'
}

worker_app.conf.imports = ("worker.tasks")
