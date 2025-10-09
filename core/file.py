import logging
import os
import subprocess

import aiohttp
import yt_dlp
import cv2
import base64
import numpy as np
from typing import TypedDict
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse


class BaseVideoFileError(Exception):
  pass


class VideoSource(ABC):
  
  def __init__(self):
    super().__init__()
    self._tmp_files: list[str] = []
  
  @abstractmethod
  def get_video_file_path(self) -> str:
    pass
  
  @abstractmethod
  def delete(self):
    pass
  
  def new_tmp_file_name(self, ext: str) -> str:
    base, _ = os.path.splitext(self.get_video_file_path())
    output_file = base + "." + ext
    self._tmp_files.append(output_file)
    return output_file

  def _delete_tmp_files(self):
    for f in self._tmp_files:
      os.remove(f)

class FilesystemVideoSource(VideoSource):
  
  def __init__(self, path: str) -> None:
    super().__init__()
    self._path = path
  
  def get_video_file_path(self) -> str:
    return self._path
  
  def delete(self):
    self._delete_tmp_files()
  

class YtDlpVideoSource(VideoSource):
  
  def __init__(self, video_url: str, download_dir: str):
    super().__init__()
    self._video_url = video_url
    self._download_dir = download_dir
    self._download()

  def _download(self):
    ydl_opts = {
      "format": "bestvideo[height<=1280]+bestaudio/best",   
      "outtmpl": f"{self._download_dir}/%(upload_date)s-%(id)s.%(ext)s",  
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
      info = ydl.extract_info(self._video_url, download=True)
      self._info = info
      self._file_path = info["requested_downloads"][0]["filepath"] # type: ignore

  def get_video_file_path(self) -> str:
    return self._file_path
  
  def delete(self):
    os.remove(self._file_path)
    self._delete_tmp_files()


class UrlVideoSourceError(BaseVideoFileError):
  pass


class UrlVideoSource(VideoSource):
  
  @classmethod
  async def new(cls, video_url: str, download_dir: str) -> "UrlVideoSource":
    source = cls(video_url, download_dir)
    await source.load()
    return source
  
  def __init__(self, video_url: str, download_dir: str):
    super().__init__()
    self._video_url = video_url
    self._download_dir = download_dir
    self._loaded = False
    
  async def load(self):
    try:
      download_dir = Path(self._download_dir)
      download_dir.mkdir(parents=True, exist_ok=True)
      
      parsed_url = urlparse(self._video_url)
      filename = Path(parsed_url.path).name
      file_path = (download_dir / filename).resolve()
      
      if file_path.exists():
        file_path.unlink(missing_ok=True)
      
      async with aiohttp.ClientSession() as session:
        async with session.get(self._video_url) as resp:
          with open(file_path, 'wb') as f:
            async for chunk in resp.content.iter_chunked(1024):
              f.write(chunk)
              
      self._file_path = file_path
      self._loaded = True
    except Exception as e:
      raise UrlVideoSourceError(f"Cannot download video: {self._video_url}") from e

  def get_video_file_path(self) -> str:
    if not self._loaded or not self._file_path:
      raise UrlVideoSourceError("File not loaded")
    
    return str(self._file_path)
  
  def delete(self):
    self._file_path.unlink(missing_ok=True) 
    self._delete_tmp_files()
  

class VideoFileError(BaseVideoFileError):
  pass


class VideoFrame(TypedDict, total=True):
  base64: str  
  frame_number: int
  timestamp: float


class VideoFile:
  
  def __init__(self, source: VideoSource):
    self._log = logging.getLogger("app:videofile")
    self._source = source
    self._open()
    
  def _open(self):
    file_path = self._source.get_video_file_path()
    cap = cv2.VideoCapture(file_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
      raise VideoFileError(f"Cannot open file: {file_path}")
    
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
    **kwargs
  ) -> list[VideoFrame]:
    interval = round(self._duration / frame_n, 2)
    if interval < min_interval:
      interval = min_interval
    
    return self.get_frames_with_interval(interval=interval, **kwargs) 
    
  def _frame_to_base64(self, frame: np.ndarray) -> str:
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode('utf-8')    


class AudioFileError(BaseVideoFileError):
  pass


class AudioFile:
  
  def __init__(self, source: VideoSource) -> None:
    self._log = logging.getLogger("app:audiofile")
    self._source = source
    self._extract_audio()
  
  def _extract_audio(self):
    input_file = self._source.get_video_file_path()
    output_file = self._source.new_tmp_file_name("mp3")
    
    if os.path.exists(output_file):
      os.remove(output_file)
    
    command = [
      "ffmpeg",
      "-i", input_file,   # input video
      "-vn",              # no video
      "-q:a", "0",        # highest quality VBR
      output_file
    ]
    
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    
    self._log.debug(f"ffmpeg finished. Exit code: {result.returncode}.")
    if result.returncode != 0:
      raise AudioFileError(f"ffmpeg error: {result.stderr}")
    
    result = Path(output_file)
    if not (result.is_file() and result.stat().st_size > 0):
      raise AudioFileError(f"output file not found or empty: {output_file}")

    self._output_file = output_file
  
  def get_audio_file_path(self) -> str:
    return self._output_file
