from fastapi import FastAPI
from workers.tasks import scrape_tiktok_videos

app = FastAPI(title="SB VideoAnalazer API", version="0.0.0")


@app.get("/health")
async def health():
  return {"ok": True}

@app.post("/scrapper/tiktok/run")
async def run_tiktok_scrapper():
  result = scrape_tiktok_videos.delay() # type: ignore
  return {"status": result.status}
