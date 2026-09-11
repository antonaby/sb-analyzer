# SB VideoAnalyzer

SB VideoAnalyzer turns short-form videos (TikTok, YouTube Shorts, ...) into structured, searchable text. Give it a topic, and it scrapes matching videos, downloads them, runs them through an AI analysis pipeline, and stores the result — frame-by-frame descriptions, spoken-word transcripts, a synopsis, topics, and (optionally) generated "challenge" content — in Postgres. Once processed, videos can be searched by their generated text via full-text search.

## How it works

The system is split into three services that share the same codebase:

- **API** (`api/`) — a FastAPI app for managing topics, challenge patterns, scraper jobs, and for triggering/inspecting workflows. It talks to Postgres directly for reads and enqueues Celery tasks for anything long-running.
- **Worker** (`worker/`) — a Celery app that runs the actual pipeline: scraping, downloading, AI analysis, categorization, translation. Tasks are composed into chains/groups (see `worker/tasks/workflows.py`) so a single "process this topic" request fans out into per-video pipelines.
- **DB** (`db/`) — SQLAlchemy (async) models and repositories on Postgres, with Alembic migrations.

### Pipeline, end to end

1. **Scrape** — `apify/` wraps Apify actors (currently an "apidojo" TikTok scraper) to search TikTok for a topic/hashtag/user and return post metadata (URL, download URL, author, likes/views/comments, hashtags, upload date).
2. **Save** — scraped posts are upserted into `videos`, `authors`, `hashtags`, and `scraped_data` (`core/processors/scraper.py`), deduplicating by URL.
3. **Download** — the video file is fetched from its CDN URL and persisted to local/object storage (`core/processors/video.py::VideoDownloadProcessor`, `core/file.py`).
4. **Analyze** — `core/processors/video.py::VideoProcessor` is the core of the product:
   - Extracts keyframes and audio from the video file (`core/video.py`, `core/file.py`).
   - Sends keyframes to a vision model (ClipTagger via inference.net) to get factual, structured descriptions of each frame — objects, actions, environment, style, logos, etc.
   - Transcribes audio via Lemonfox (Whisper-style API).
   - Runs a `pydantic-ai` agent (`core/agents/summary.py`) that reads the post metadata, transcript, and frame data (pulling extra frames on demand via an agent tool) to produce a label, synopsis, key actions, and topics for the video.
   - All of this — frame annotations, transcript segments, summary, post metadata — is written as `VideoAnnotation`/`VideoMeta` rows against the video, each with a generated Postgres `tsvector` column for full-text search.
5. **Categorize** — a second agent (`core/agents/topic.py`) assigns the video to one or more user-defined topics with a confidence score, given the analyzed text and the topic list.
6. **Generate challenges** *(optional)* — `core/agents/challenge.py` turns a video's content into "challenge" entries matched against configurable patterns, then categorizes and translates them (`core/processors/challenge.py`, `core/agents/translation.py`).
7. **Search** — `GET /videos` runs a Postgres full-text query (`plainto_tsquery`) across a video's annotations and meta to find matching videos; `GET /videos/{id}` returns the full assembled record.

### Orchestration

A single API call (e.g. `POST /workflows/apidojo`) kicks off a Celery `chain`/`group` that scrapes → saves → (per new video) downloads → analyzes → categorizes → generates challenges, tracked per-video via a `Workflow`/`VideoProcessing` row so progress and errors are auditable. A scheduled Celery Beat job also periodically runs enabled scraper jobs (`worker/main.py`).

## Project layout

```
api/          FastAPI app: routers, dependencies
worker/       Celery app and tasks (workflow orchestration)
core/         Business logic: agents (LLM calls), processors (pipeline steps),
              video/audio/file handling, transcription
apify/        Apify/TikTok scraper client wrappers
db/           SQLAlchemy models and repositories, DB config
models/       Pydantic request/spec models shared between API and worker
alembic/      DB migrations
notebooks/    Exploratory/dev notebooks for each pipeline stage
utils/        Small shared helpers
```

## Stack

- **API**: FastAPI
- **Task queue**: Celery (Redis broker), Celery Beat for scheduled scraping
- **Database**: PostgreSQL via SQLAlchemy (async) + Alembic migrations
- **AI**: `pydantic-ai` agents on OpenAI / Google Gemini models, ClipTagger (inference.net) for frame vision, Lemonfox for transcription
- **Scraping**: Apify actors (TikTok)
- **Video/audio**: OpenCV, yt-dlp
- **Observability**: Logfire (FastAPI, Celery, SQLAlchemy, pydantic-ai instrumentation)

## Running locally

Dependencies are managed with `uv` (see `pyproject.toml` dependency groups: `api`, `db`, `ai`, `migrations`, `monitoring`, `dev`).

```bash
uv sync --group api --group db --group ai --group migrations

# API
uv run fastapi dev api/main.py

# Worker
uv run celery -A worker.main.worker_app worker -B
```

Required environment variables (see `.env`): `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_DATABASE_URL`, `APIFY_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `INFERENCE_API_KEY`, `LEMONFOX_API_KEY`, `LOCAL_VIDEO_STORAGE_PATH`, plus optional `SCAPER_JOB_CRON` and Logfire settings.
