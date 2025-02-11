# type: ignore
from typing import AsyncGenerator

import extract_msg

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class MSGParser(AsyncParser[str | bytes]):
    """Parser for MSG (Outlook Message) files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.extract_msg = extract_msg

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest MSG data and yield email content."""
        if isinstance(data, str):
            raise ValueError("MSG data must be in bytes format.")

        from io import BytesIO

        file_obj = BytesIO(data)

        try:
            msg = self.extract_msg.Message(file_obj)

            # Extract metadata
            metadata = []
            if msg.subject:
                metadata.append(f"Subject: {msg.subject}")
            if msg.sender:
                metadata.append(f"From: {msg.sender}")
            if msg.to:
                metadata.append(f"To: {msg.to}")
            if msg.date:
                metadata.append(f"Date: {msg.date}")

            if metadata:
                yield "\n".join(metadata)

            # Extract body
            if msg.body:
                yield msg.body.strip()

            # Extract attachments (optional)
            for attachment in msg.attachments:
                if hasattr(attachment, "name"):
                    yield f"\nAttachment: {attachment.name}"

        except Exception as e:
            raise ValueError(f"Error processing MSG file: {str(e)}")
        finally:
            file_obj.close()
