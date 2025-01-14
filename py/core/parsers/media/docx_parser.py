from io import BytesIO
from typing import AsyncGenerator

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

        try:
            from docx import Document

            self.Document = Document
        except ImportError:
            raise ValueError(
                "Error, `python-docx` is required to run `DOCXParser`. Please install it using `pip install python-docx`."
            )

    async def ingest(self, data: str | bytes, *args, **kwargs) -> AsyncGenerator[str, None]:  # type: ignore
        """Ingest DOCX data and yield text from each paragraph."""
        if isinstance(data, str):
            raise ValueError("DOCX data must be in bytes format.")

        doc = self.Document(BytesIO(data))
        for paragraph in doc.paragraphs:
            yield paragraph.text
