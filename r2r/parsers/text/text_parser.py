from typing import AsyncGenerator

from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser


class TextParser(AsyncParser[DataType]):
    """A parser for raw text data."""

    async def ingest(self, data: DataType) -> AsyncGenerator[DataType, None]:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        yield data
