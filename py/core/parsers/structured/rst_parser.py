# type: ignore
from typing import AsyncGenerator

from docutils.core import publish_string
from docutils.writers import html5_polyglot

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class RSTParser(AsyncParser[str | bytes]):
    """Parser for reStructuredText (.rst) files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.publish_string = publish_string
        self.html5_polyglot = html5_polyglot

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        try:
            # Convert RST to HTML
            html = self.publish_string(
                source=data,
                writer=self.html5_polyglot.Writer(),
                settings_overrides={"report_level": 5},
            )

            # Basic HTML cleanup
            import re

            text = html.decode("utf-8")
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)

            # Split into paragraphs and yield non-empty ones
            paragraphs = text.split("\n\n")
            for paragraph in paragraphs:
                if paragraph.strip():
                    yield paragraph.strip()

        except Exception as e:
            raise ValueError(f"Error processing RST file: {str(e)}") from e
