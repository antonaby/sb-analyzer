from fastapi import FastAPI

from api.deps import *
from api.routes import videos, tasks, topics, authors, challenges, scrapers, workflows
from db.conf import test_db_conn

app = FastAPI(title="SB VideoAnalyzer API", version="0.0.0")
logfire.instrument_fastapi(app)

app.include_router(authors.router)
app.include_router(videos.router)
app.include_router(tasks.router)
app.include_router(topics.router)
app.include_router(challenges.router)
app.include_router(scrapers.router)
app.include_router(workflows.router)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_async_db)):
  result = await test_db_conn(db)
  db_status = result is not None and result == 1
  
  return {
    "db": db_status
  }
