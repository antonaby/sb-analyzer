from pydantic import BaseModel
from core.utils import var_or_exception
from core.videos import AudioFile
import aiohttp


LEMONFOX_API_KEY_VAR = "LEMONFOX_API_KEY"
LEMONFOX_API_URL = "https://api.lemonfox.ai/v1/audio/transcriptions"

class Word(BaseModel):
  word: str = ""
  start: float = 0
  end: float = 0
  score: float = 0
  speaker: str | None = ""


class Segment(BaseModel):
  id: int = 0
  text: str = ""
  start: float = 0
  end: float = 0
  avg_logprob: float = 0
  language: str = "en"
  speaker: str | None = ""
  words: list[Word] = []


class Transcript(BaseModel):
  task: str = ""
  language: str = "en"
  duration: float = 0
  text: str = ""
  segments: list[Segment] = []


class LemonfoxClientError(Exception):
  pass


class LemonfoxClient:
  
  def __init__(self, url=LEMONFOX_API_URL):
    self._key = var_or_exception(LEMONFOX_API_KEY_VAR)
    self._url = url
  
  async def transcribe(self, file: AudioFile, **kwargs) -> Transcript:
    headers = {
      "Authorization": f"Bearer {self._key}"
    }
    
    file_path = file.get_audio_file_path()
    
    try:
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
            result = await response.json()
            return Transcript.model_validate(result)
    except Exception as e:
      raise LemonfoxClientError(f"Cannot transcribe audio file: {file_path}") from e
    
  