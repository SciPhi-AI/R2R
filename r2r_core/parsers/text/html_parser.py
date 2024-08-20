from typing import AsyncGenerator

from bs4 import BeautifulSoup

from r2r_core.base.abstractions.document import DataType
from r2r_core.base.parsers.base_parser import AsyncParser


class HTMLParser(AsyncParser[DataType]):
    """A parser for HTML data."""

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest HTML data and yield text."""
        soup = BeautifulSoup(data, "html.parser")
        yield soup.get_text()
