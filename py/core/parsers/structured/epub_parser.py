# type: ignore
import logging
from typing import AsyncGenerator

import epub

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger(__name__)


class EPUBParser(AsyncParser[str | bytes]):
    """Parser for EPUB electronic book files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.epub = epub

    def _safe_get_metadata(self, book, field: str) -> str | None:
        """Safely extract metadata field from epub book."""
        try:
            return getattr(book, field, None) or getattr(book.opf, field, None)
        except Exception as e:
            logger.debug(f"Error getting {field} metadata: {e}")
            return None

    def _clean_text(self, content: bytes) -> str:
        """Clean HTML content and return plain text."""
        try:
            import re

            text = content.decode("utf-8", errors="ignore")
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text)
            # Remove any remaining HTML entities
            text = re.sub(r"&[^;]+;", " ", text)
            return text.strip()
        except Exception as e:
            logger.warning(f"Error cleaning text: {e}")
            return ""

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest EPUB data and yield book content."""
        if isinstance(data, str):
            raise ValueError("EPUB data must be in bytes format.")

        from io import BytesIO

        file_obj = BytesIO(data)

        try:
            book = self.epub.open_epub(file_obj)

            # Safely extract metadata
            metadata = []
            for field, label in [
                ("title", "Title"),
                ("creator", "Author"),
                ("language", "Language"),
                ("publisher", "Publisher"),
                ("date", "Date"),
            ]:
                if value := self._safe_get_metadata(book, field):
                    metadata.append(f"{label}: {value}")

            if metadata:
                yield "\n".join(metadata)

            # Extract content from items
            try:
                manifest = getattr(book.opf, "manifest", {}) or {}
                for item in manifest.values():
                    try:
                        if (
                            getattr(item, "mime_type", "")
                            == "application/xhtml+xml"
                        ):
                            if content := book.read_item(item):
                                if cleaned_text := self._clean_text(content):
                                    yield cleaned_text
                    except Exception as e:
                        logger.warning(f"Error processing item: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Error accessing manifest: {e}")
                # Fallback: try to get content directly
                if hasattr(book, "read_item"):
                    for item_id in getattr(book, "items", []):
                        try:
                            if content := book.read_item(item_id):
                                if cleaned_text := self._clean_text(content):
                                    yield cleaned_text
                        except Exception as e:
                            logger.warning(f"Error in fallback reading: {e}")
                            continue

        except Exception as e:
            logger.error(f"Error processing EPUB file: {str(e)}")
            raise ValueError(f"Error processing EPUB file: {str(e)}") from e
        finally:
            try:
                file_obj.close()
            except Exception as e:
                logger.warning(f"Error closing file: {e}")
