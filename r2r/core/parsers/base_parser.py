"""Abstract base class for parsers."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Generic, TypeVar

from ..abstractions.document import DataType

T = TypeVar("T")


class AsyncParser(ABC, Generic[T]):
    @abstractmethod
    async def ingest(self, data: T) -> AsyncGenerator[DataType, None]:
        pass
