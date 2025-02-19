# type: ignore
import struct
from io import BytesIO
from typing import AsyncGenerator

import olefile

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class PPTParser(AsyncParser[str | bytes]):
    """A parser for legacy PPT (PowerPoint 97-2003) files."""

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

    def _extract_text_from_record(self, data: bytes) -> str:
        """Extract text from a PPT text record."""
        try:
            # Skip record header
            text_data = data[8:]
            # Convert from UTF-16-LE
            return text_data.decode("utf-16-le", errors="ignore").strip()
        except Exception:
            return ""

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest PPT data and yield text from each slide."""
        if isinstance(data, str):
            raise ValueError("PPT data must be in bytes format.")

        try:
            ole = self.olefile.OleFileIO(BytesIO(data))

            # PPT stores text in PowerPoint Document stream
            if not ole.exists("PowerPoint Document"):
                raise ValueError("Not a valid PowerPoint file")

            # Read PowerPoint Document stream
            ppt_stream = ole.openstream("PowerPoint Document")
            content = ppt_stream.read()

            # Text records start with 0x0FA0 or 0x0FD0
            text_markers = [b"\xa0\x0f", b"\xd0\x0f"]

            current_position = 0
            while current_position < len(content):
                # Look for text markers
                for marker in text_markers:
                    marker_pos = content.find(marker, current_position)
                    if marker_pos != -1:
                        # Get record size from header (4 bytes after marker)
                        size_bytes = content[marker_pos + 2 : marker_pos + 6]
                        record_size = struct.unpack("<I", size_bytes)[0]

                        # Extract record data
                        record_data = content[
                            marker_pos : marker_pos + record_size + 8
                        ]
                        text = self._extract_text_from_record(record_data)

                        if text.strip():
                            yield text.strip()

                        current_position = marker_pos + record_size + 8
                        break
                else:
                    current_position += 1

        except Exception as e:
            raise ValueError(f"Error processing PPT file: {str(e)}") from e
        finally:
            ole.close()
