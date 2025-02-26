# type: ignore
from io import BytesIO
from typing import AsyncGenerator

from docx import Document

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class DOCXParser(AsyncParser[str | bytes]):
    """A parser for DOCX data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.Document = Document

    async def ingest(
        self, data: str | bytes, *args, **kwargs
    ) -> AsyncGenerator[str, None]:  # type: ignore
        """Ingest DOCX data and yield text from each paragraph."""
        if isinstance(data, str):
            raise ValueError("DOCX data must be in bytes format.")

        doc = self.Document(BytesIO(data))
        for paragraph in doc.paragraphs:
            yield paragraph.text
