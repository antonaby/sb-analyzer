import logging
import os
import subprocess

import yt_dlp
import cv2
import base64
import numpy as np
from typing import TypedDict
from tempfile import NamedTemporaryFile


class VideoFileError(Exception):
  pass

class VideoFrame(TypedDict, total=True):
  base64: str  
  frame_number: int
  timestamp: float

class VideoFile:
  
  def __init__(self, path: str):
    self._log = logging.getLogger("app:videofile")
    self._file_path = path
    self._open()
    
  def _open(self):
    cap = cv2.VideoCapture(self._file_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
      raise VideoFileError(f"Cannot open file: {self._file_path}")
    
    self._cap = cap
    self._fps = cap.get(cv2.CAP_PROP_FPS)
    self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    self._duration = self._total_frames / self._fps

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    self._log.debug(f"Video info: {self._duration:.1f}s duration, {self._fps:.1f} fps, width {width}, height {height}")
    
  def get_duration(self) -> float:
    return self._duration
  
  def get_total_frames(self) -> int:
    return self._total_frames
  
  def close(self):
    self._cap.release()
  
  def get_frame(self, timestamp: float) -> VideoFrame:
    if timestamp > self._duration or timestamp < 0:
      raise VideoFileError(f"out of video duration: {timestamp}, duration: {self._duration}")
    
    frame_number = min(int(timestamp * self._fps), self._total_frames - 1)
    self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = self._cap.read()

    if not ret:
      raise VideoFileError(f"Cannot get frame at: {timestamp}")
    
    self._log.debug(f"Extracted frame at {timestamp:.1f}s")
    return {
      'base64': self._frame_to_base64(frame),
      'frame_number': frame_number,
      'timestamp': round(timestamp, 2)
    }
    
  def get_frames_with_interval(
    self, 
    start_timestamp: float = 0.1, 
    interval: float = 10,
    include_last: bool = True,
    last_before: float = 0.1
  ) -> list[VideoFrame]:
    frames: list[VideoFrame] = []
    current_time = start_timestamp
    
    while current_time < self._duration:
      frames.append(self.get_frame(current_time))
      current_time += interval
      
    if include_last:
      last_frame_timestamp = self._duration - last_before
      last_step_timestamp = current_time - interval
      if last_frame_timestamp > last_step_timestamp:
        frames.append(self.get_frame(last_frame_timestamp))
      else:
        frames.append(self.get_frame(last_step_timestamp))

    return frames

  def get_n_frames(
    self,
    frame_n: int = 5, 
    min_interval: float = 3.0, 
    *args, **kwargs
  ) -> list[VideoFrame]:
    interval = round(self._duration / frame_n, 2)
    if interval < min_interval:
      interval = min_interval
    
    return self.get_frames_with_interval(interval=interval, *args, **kwargs) 
    
  def _frame_to_base64(self, frame: np.ndarray) -> str:
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode('utf-8')    
  
  # def get_audio(self) -> bytes:
  #   pass

  
class VideoDetails(TypedDict, total=True):
  frames: list[VideoFrame]
  audio: bytes

def split_video(data: bytes, interval_seconds: float = 1.0) -> VideoDetails: 
  with NamedTemporaryFile(delete=False, suffix=".mp4") as f:
    f.write(data)
    tmp_file = f.name
   
  frames = _split_video(tmp_file, interval_seconds)
  audio = _extract_audio(tmp_file)  
  os.remove(tmp_file)
  
  return {
    "frames": frames,
    "audio": audio
  }
    
def _split_video(path: str, interval_seconds) -> list[VideoFrame]:
  log = logging.getLogger("analyzer")
  
  cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
  if not cap.isOpened():
    raise ValueError(f"Cannot open file: {path}")
  
  fps = cap.get(cv2.CAP_PROP_FPS)
  total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
  duration = total_frames / fps

  width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
  height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
  
  log.debug(f"Video info: {duration:.1f}s duration, {fps:.1f} fps, width {width}, height {height}")
  
  frames: list[VideoFrame] = []
  current_time = 0
  
  while current_time < duration:
    frame_number = int(current_time * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()

    if ret:
      frames.append({
        'base64': _frame_to_base64(frame),
        'frame_number': frame_number,
        'timestamp': current_time
      })
      log.debug(f"  Extracted frame at {current_time:.1f}s")

    current_time += interval_seconds

  cap.release()
  log.debug(f"Extracted {len(frames)} frames")
  
  return frames

def _frame_to_base64(frame: np.ndarray) -> str:
  _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
  return base64.b64encode(buffer).decode('utf-8')    

def _extract_audio(input_file: str) -> bytes:
  base, _ = os.path.splitext(input_file)
  output_file = base + ".mp3"
  
  command = [
    "ffmpeg",
    "-i", input_file,   # input video
    "-vn",              # no video
    "-q:a", "0",        # highest quality VBR
    output_file
  ]
  
  result = subprocess.run(command, check=True, capture_output=True, text=True)
  
  log = logging.getLogger("analyzer")
  log.debug(f"ffmpeg finished. Exit code: {result.returncode}.")
  if result.returncode != 0:
    log.error(f"ffmpeg error: {result.stderr}")
  
  with open(output_file, "rb") as f:
    data = f.read()
  
  os.remove(output_file)
  return data

def download_yt_video(url: str, path: str):
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