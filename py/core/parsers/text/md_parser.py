# type: ignore
from typing import AsyncGenerator

from bs4 import BeautifulSoup

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class MDParser(AsyncParser[str | bytes]):
    """A parser for Markdown data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

        import markdown

        self.markdown = markdown

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest Markdown data and yield text."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        html = self.markdown.markdown(data)
        soup = BeautifulSoup(html, "html.parser")
        yield soup.get_text()
