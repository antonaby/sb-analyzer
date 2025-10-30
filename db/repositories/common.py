from abc import ABC, abstractmethod
from typing import Final


class BadDataRepositoryError(Exception):
  pass


class BaseAsyncRepo(ABC):
  
  @abstractmethod
  async def commit(self):
    pass


REGCONFIG_BY_LANG: Final[dict[str, str]] = {
  "en": "english",
  "fr": "french",
  "de": "german",
  "es": "spanish",
  "it": "italian",
  "pt": "portuguese",
  "ru": "russian",
  "nl": "dutch",
  "sv": "swedish",
  "no": "norwegian",
  "da": "danish",
  "fi": "finnish",
  "ro": "romanian",
  "hu": "hungarian",
  "tr": "turkish",
  "cs": "czech",
  "ar": "arabic",
  "zh": "simple",
  "ja": "simple",
}


def regconfig_for(lang: str) -> str:
  return REGCONFIG_BY_LANG.get(lang.lower(), "english")
