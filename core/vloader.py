import yt_dlp
import cv2
import base64
from typing import Dict, List
import numpy as np


def download_video(url: str, path: str):
  ydl_opts = {
    "format": "bestvideo[height<=1280]+bestaudio/best",   
    "outtmpl": f"{path}/%(upload_date)s-%(id)s.%(ext)s",  
    "quiet": True,                                        
    "noplaylist": True,                                   
    "postprocessors": [
      {  
        "key": "FFmpegVideoConvertor",
        "preferedformat": "mp4",
      }
    ],
  }

  with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
    info = ydl.extract_info(url, download=True)
    return info
    
def frame_to_base64(frame: np.ndarray) -> str:
  # Encode as JPEG
  _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
  # Convert to base64
  return base64.b64encode(buffer).decode('utf-8')    
    
# TODO: add better logging
def extract_video(path: str, interval_seconds: float = 1.0) -> List[Dict]:
  cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
  if not cap.isOpened():
    raise ValueError(f"Cannot open video: {path}")
  
  fps = cap.get(cv2.CAP_PROP_FPS)
  total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  duration = total_frames / fps

  width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
  height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

  print(f"Video info: {duration:.1f}s duration, {fps:.1f} fps, width {width}, height {height}")
  
  frames = []
  current_time = 0
  
  while current_time < duration:
    frame_number = int(current_time * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()

    if ret:
      frames.append({
        'frame': frame_to_base64(frame),
        'frame_number': frame_number,
        'timestamp': current_time
      })
      print(f"  Extracted frame at {current_time:.1f}s")

    current_time += interval_seconds

  cap.release()
  print(f"Extracted {len(frames)} frames")
  return frames
