import asyncio
from typing import TypedDict
from pydantic import BaseModel
from utils.common import var_or_exception
from core.file import AudioFile
import aiohttp


LEMONFOX_API_KEY_VAR = "LEMONFOX_API_KEY"
LEMONFOX_API_URL = "https://api.lemonfox.ai/v1/audio/transcriptions"

class Word(TypedDict, total=False):
  word: str
  start: float
  end: float
  score: float
  speaker: str


class Segment(TypedDict, total=False):
  id: int
  text: str
  start: float
  end: float
  avg_logprob: float
  language: str
  speaker: str
  words: list[Word]


class Transcript(TypedDict, total=False):
  task: str
  language: str
  duration: float
  text: str
  segments: list[Segment]


class LemonfoxClientError(Exception):
  pass


class LemonfoxClient:
  
  def __init__(self, concurrency: int = 20, url=LEMONFOX_API_URL):
    self._key = var_or_exception(LEMONFOX_API_KEY_VAR)
    self._url = url
    self._api_semaphore = asyncio.Semaphore(concurrency)
  
  async def transcribe(self, file_path: str, **kwargs) -> Transcript:
    
    headers = {
      "Authorization": f"Bearer {self._key}"
    }
    
    try:
      async with self._api_semaphore:
        with open(file_path, 'rb') as f:
          form = aiohttp.FormData()
          form.add_field("response_format", kwargs.get("response_format", "verbose_json"))
          form.add_field("speaker_labels", kwargs.get("speaker_labels", "true"))
          form.add_field("translate", kwargs.get("translate", "true"))
          
          form.add_field(
            'file',              
            f,                   
            filename=file_path.split("/")[-1],
            content_type="audio/mpeg"
          )

          async with aiohttp.ClientSession() as session:
            async with session.post(self._url, headers=headers, data=form) as response:
              result: Transcript = await response.json()
              return result
    except Exception as e:
      raise LemonfoxClientError(f"Cannot transcribe audio file: {file_path}") from e

class Transcription(BaseModel):
  text: str = ""
  start_sec: float = 0
  end_sec: float = 0


class FileAudioData:
  
  def __init__(self, lm_client: LemonfoxClient, audio_file: AudioFile):
    self._lm_client = lm_client
    self._audio_file = audio_file
    self._trans_cache: list[Transcription] = []
  
  def get_processed_transcriptions(self) ->  list[Transcription]:
    return self._trans_cache
    
  async def get_transcription(self) -> list[Transcription]:
    file_path = self._audio_file.get_audio_file_path()
    trans = await self._lm_client.transcribe(file_path)
    
    self._trans_cache = [
      Transcription(
        text=s.get("text", "no text"), 
        start_sec=s.get("start", 0),
        end_sec=s.get("end", 0)
      ) 
      for s in trans.get("segments", [])
    ]
    
    return self._trans_cache