# AGENTS.md

Instructions for AI coding agents working in this repository. See `README.md` for a description of what the product does.

## Database migrations

- Agents **are allowed to create/author new Alembic migrations** (e.g. via `uv run alembic revision --autogenerate -m "..."`, or by hand under `alembic/versions/`) when a model change requires one.
- Agents **are not allowed to apply migrations** against any database (no `uv run alembic upgrade ...`, no equivalent SQL run by hand). Generate the migration, review it for correctness (column types, nullability, indexes, `include_object` exclusions in `alembic/env.py`), and leave applying it to the user.
- Never run destructive schema operations (`alembic downgrade`, manual `DROP`/`ALTER` against a live DB) under any circumstances.
- Migrations are generated from `db/models/*` (`Base.metadata` in `db/conf.py`). Keep model changes and their migration in the same change set; don't let them drift.

## Tech stack and how to work with it

- **Python 3.13**, dependency management via `uv` / `pyproject.toml` dependency groups (`api`, `db`, `ai`, `migrations`, `dev`, `monitoring`). Install what you need with `uv sync --group <name>`; don't `pip install` directly.
- **FastAPI** (`api/`) — routers live in `api/routes/*`, wired up in `api/main.py`. Dependencies (DB session, repositories) are provided via `api/deps.py` using FastAPI's `Depends`. Route handlers should stay thin: validate input, call a repository or enqueue a Celery task, return a Pydantic model.
- **Celery** (`worker/`) — long-running/AI work goes through Celery tasks (`worker/tasks/*`), never runs synchronously inside an API request. Multi-step pipelines are composed with `chain`/`group`/`chord` in `worker/tasks/workflows.py`; follow that pattern rather than calling processors directly from a task chain ad hoc. Tasks that need an event loop use the shared `loop`/session helpers in `worker/tasks/deps.py`.
- **SQLAlchemy (async)** (`db/`) — models in `db/models/*`, one repository per aggregate in `db/repositories/*` (all extending `BaseAsyncRepo`). Keep DB access behind a repository; don't write raw queries in `core/` or `api/` code. Repositories take a session and don't commit themselves except via an explicit `commit()` — callers control transaction boundaries.
- **pydantic-ai agents** (`core/agents/*`) — each agent wraps a `pydantic_ai.Agent` with a structured `output_type` (`Config.extra = "forbid"` on response models) and Jinja2 prompt templates (`core/agents/templates/*.jinja`, rendered via `TemplateManager`). When adding a new agent capability, prefer adding a template + typed input/output models over freeform string prompts, and keep model/provider selection in `core/agents/common.py`.
- **External AI services**: ClipTagger via inference.net (frame vision, `core/video.py`), Lemonfox (transcription, `core/transcribe.py`), OpenAI/Google Gemini (agents). All require API keys from env (`utils.common.var_or_exception`) — never hardcode keys, and fail loudly (as the existing code does) if a required var is missing rather than silently degrading.
- **Apify / scraping** (`apify/`) — TikTok scraping goes through `ApifyClient` wrappers; scraped payloads are stored as-is in `scraped_data.data` (JSONB) alongside normalized fields, so schema changes to scraper output don't require a migration unless you also want to query/index the new field.
- **Search** relies on generated Postgres `tsvector` columns (`value_tsv` on `video_meta` / `video_annotations`) with GIN indexes — if you add a new text-bearing column that should be searchable, follow that same `Computed(...)` + GIN index pattern rather than building search some other way.
- **Notebooks** (`notebooks/`) are exploratory/dev scratch space mirroring pipeline stages; they are not part of the shipped app and don't need to be kept in sync with refactors unless asked.

## Project structure quick reference

```
api/          FastAPI app, routers, request/response models
worker/       Celery app + tasks, workflow orchestration (chains/groups)
core/         agents/ (LLM calls), processors/ (pipeline steps), video/audio/file handling
apify/        Apify + TikTok scraper client wrappers
db/           SQLAlchemy models (db/models) and repositories (db/repositories)
models/       Pydantic spec/request models shared between api and worker task payloads
alembic/      migrations (author only, do not apply — see above)
utils/        small shared helpers (env var access, logfire config)
```

## General conventions

- Indentation is 2 spaces throughout the codebase (not 4) — match the surrounding file.
- Pydantic models used as agent outputs set `class Config: extra = "forbid"` — keep doing this for new structured-output models so the LLM can't silently add unexpected fields.
- Processors (`core/processors/*`) follow a `run(spec) -> Result` / `run_workflow(spec, video_processing_id)` pattern where `run_workflow` wraps `run` to record success/error timestamps on `VideoProcessing`. Follow this pattern for new pipeline steps rather than inventing a new status-tracking mechanism.
- Env vars are read via `utils.common.var_or_exception`, which raises if the var is unset — use it for any new required config instead of `os.getenv` with a silent default.
