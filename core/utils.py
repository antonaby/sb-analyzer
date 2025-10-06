import os


def var_or_exception(key: str) -> str:
  key_value = os.getenv(key)
  if not key_value or not key_value.strip():
    raise EnvironmentError(f"{key} not set or empty")  
  
  return key_value
  