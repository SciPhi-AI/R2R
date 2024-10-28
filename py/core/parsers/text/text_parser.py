# type: ignore
from typing import AsyncGenerator

from core.base.abstractions import DataType
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class TextParser(AsyncParser[DataType]):
    """A parser for raw text data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

    async def ingest(
        self, data: DataType, *args, **kwargs
    ) -> AsyncGenerator[DataType, None]:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        yield data
