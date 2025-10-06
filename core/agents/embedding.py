import logging
import os
import numpy as np
from openai import AsyncOpenAI
from openai.types.embedding import Embedding


INFERENCE_API_KEY_VAR = "INFERENCE_API_KEY"

class Embedder:
  
  def __init__(self):
    self._log = logging.getLogger("app.embedder")
    
    inference_key = os.getenv(INFERENCE_API_KEY_VAR)
    if not inference_key or not inference_key.strip():
      raise EnvironmentError(f"{INFERENCE_API_KEY_VAR} not set or empty")
      
    self._client = AsyncOpenAI(
      base_url="https://api.inference.net/v1",
      api_key=inference_key
    )
    
  async def get_embeddings(self, value: str) -> np.ndarray: 
    response = await self._client.embeddings.create(
      model="qwen/qwen3-embedding-4b",
      input=value,
      encoding_format="float"
    )
    
    # TODO: get all produced embeddings
    result = np.array(response.data[0].embedding, dtype=np.float32)
    return result
