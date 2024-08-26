from typing import AsyncGenerator

from bs4 import BeautifulSoup

from core.base.abstractions.document import DataType
from core.base.parsers.base_parser import AsyncParser


class MDParser(AsyncParser[DataType]):
    """A parser for Markdown data."""

    def __init__(self):
        import markdown

        self.markdown = markdown

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest Markdown data and yield text."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        html = self.markdown.markdown(data)
        soup = BeautifulSoup(html, "html.parser")
        yield soup.get_text()
