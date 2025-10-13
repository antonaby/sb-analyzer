from abc import ABC, abstractmethod


class BaseAsyncRepo(ABC):
  
  @abstractmethod
  async def commit(self):
    pass