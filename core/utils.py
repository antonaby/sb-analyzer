import os
from urllib.parse import urlparse


def var_or_exception(key: str) -> str:
  key_value = os.getenv(key)
  if not key_value or not key_value.strip():
    raise EnvironmentError(f"{key} not set or empty")  
  
  return key_value


def is_url(s: str) -> bool:
  if not str or not s.strip(): 
    return False
  
  result = urlparse(s)
  return all([result.scheme in ("http", "https"), result.netloc])
  