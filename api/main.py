import logfire
from fastapi import FastAPI

from api.deps import *
from api.routes import videos, jobs, queue, topics, authors, runs, challenges, scrapers
from db.conf import test_db_conn


app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")
logfire.instrument_fastapi(app)

app.include_router(authors.router)
app.include_router(videos.router)
app.include_router(jobs.router)
app.include_router(queue.router)
app.include_router(topics.router)
app.include_router(runs.router)
app.include_router(challenges.router)
app.include_router(scrapers.router)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_async_db)):
  result = await test_db_conn(db)
  db_status = result is not None and result == 1
  
  return {
    "db": db_status
  }
