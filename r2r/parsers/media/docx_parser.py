from io import BytesIO
from typing import AsyncGenerator

from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser


class DOCXParser(AsyncParser[DataType]):
    """A parser for DOCX data."""

    def __init__(self):
        try:
            from docx import Document

            self.Document = Document
        except ImportError:
            raise ValueError(
                "Error, `python-docx` is required to run `DOCXParser`. Please install it using `pip install python-docx`."
            )

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest DOCX data and yield text from each paragraph."""
        if isinstance(data, str):
            raise ValueError("DOCX data must be in bytes format.")

        doc = self.Document(BytesIO(data))
        for paragraph in doc.paragraphs:
            yield paragraph.text
