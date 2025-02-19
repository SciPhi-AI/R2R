# type: ignore
import re
from io import BytesIO
from typing import AsyncGenerator

import olefile

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class DOCParser(AsyncParser[str | bytes]):
    """A parser for DOC (legacy Microsoft Word) data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.olefile = olefile

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest DOC data and yield text from the document."""
        if isinstance(data, str):
            raise ValueError("DOC data must be in bytes format.")

        # Create BytesIO object from the data
        file_obj = BytesIO(data)

        try:
            # Open the DOC file using olefile
            ole = self.olefile.OleFileIO(file_obj)

            # Check if it's a Word document
            if not ole.exists("WordDocument"):
                raise ValueError("Not a valid Word document")

            # Read the WordDocument stream
            word_stream = ole.openstream("WordDocument").read()

            # Read the text from the 0Table or 1Table stream (contains the text)
            if ole.exists("1Table"):
                table_stream = ole.openstream("1Table").read()
            elif ole.exists("0Table"):
                table_stream = ole.openstream("0Table").read()
            else:
                table_stream = b""

            # Extract text content
            text = self._extract_text(word_stream, table_stream)

            # Clean and split the text
            paragraphs = self._clean_text(text)

            # Yield non-empty paragraphs
            for paragraph in paragraphs:
                if paragraph.strip():
                    yield paragraph.strip()

        except Exception as e:
            raise ValueError(f"Error processing DOC file: {str(e)}") from e
        finally:
            ole.close()
            file_obj.close()

    def _extract_text(self, word_stream: bytes, table_stream: bytes) -> str:
        """Extract text from Word document streams."""
        try:
            text = word_stream.replace(b"\x00", b"").decode(
                "utf-8", errors="ignore"
            )

            # If table_stream exists, try to extract additional text
            if table_stream:
                table_text = table_stream.replace(b"\x00", b"").decode(
                    "utf-8", errors="ignore"
                )
                text += table_text

            return text
        except Exception as e:
            raise ValueError(f"Error extracting text: {str(e)}") from e

    def _clean_text(self, text: str) -> list[str]:
        """Clean and split the extracted text into paragraphs."""
        # Remove binary artifacts and control characters
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\xFF]", "", text)

        # Remove multiple spaces and newlines
        text = re.sub(r"\s+", " ", text)

        # Split into paragraphs on double newlines or other common separators
        paragraphs = re.split(r"\n\n|\r\n\r\n|\f", text)

        # Remove empty or whitespace-only paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        return paragraphs
