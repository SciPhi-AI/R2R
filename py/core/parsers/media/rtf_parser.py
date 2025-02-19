# type: ignore
from typing import AsyncGenerator

from striprtf.striprtf import rtf_to_text

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class RTFParser(AsyncParser[str | bytes]):
    """Parser for Rich Text Format (.rtf) files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.striprtf = rtf_to_text

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        try:
            # Convert RTF to plain text
            plain_text = self.striprtf(data)

            # Split into paragraphs and yield non-empty ones
            paragraphs = plain_text.split("\n\n")
            for paragraph in paragraphs:
                if paragraph.strip():
                    yield paragraph.strip()

        except Exception as e:
            raise ValueError(f"Error processing RTF file: {str(e)}") from e
