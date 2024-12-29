"""Abstract base class for parsers."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Generic, TypeVar

T = TypeVar("T")


class AsyncParser(ABC, Generic[T]):
    @abstractmethod
    async def ingest(self, data: T, **kwargs) -> AsyncGenerator[str, None]:
        pass
