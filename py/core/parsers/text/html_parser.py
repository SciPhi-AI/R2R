# type: ignore
from typing import AsyncGenerator

from bs4 import BeautifulSoup

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class HTMLParser(AsyncParser[str | bytes]):
    """A parser for HTML data."""

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
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest HTML data and yield text."""
        soup = BeautifulSoup(data, "html.parser")
        yield soup.get_text()
