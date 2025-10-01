from .main import app

@app.task
def scrape_tiktok_videos() -> int:
  return 0
