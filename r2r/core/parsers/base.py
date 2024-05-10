from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Generic, TypeVar


from ..abstractions.document import DataType

T = TypeVar("T")


class AsyncParser(ABC, Generic[T]):
    @abstractmethod
    async def ingest(self, data: Any) -> AsyncGenerator[DataType, None]:
        pass
