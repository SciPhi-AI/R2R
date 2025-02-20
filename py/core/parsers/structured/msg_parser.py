# type: ignore
import os
import tempfile
from typing import AsyncGenerator

from msg_parser import MsOxMessage

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class MSGParser(AsyncParser[str | bytes]):
    """Parser for MSG (Outlook Message) files using msg_parser."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest MSG data and yield email content."""
        if isinstance(data, str):
            raise ValueError("MSG data must be in bytes format.")

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".msg")
        try:
            tmp_file.write(data)
            tmp_file.close()

            msg = MsOxMessage(tmp_file.name)

            metadata = []

            if msg.subject:
                metadata.append(f"Subject: {msg.subject}")
            if msg.sender:
                metadata.append(f"From: {msg.sender}")
            if msg.to:
                metadata.append(f"To: {', '.join(msg.to)}")
            if msg.sent_date:
                metadata.append(f"Date: {msg.sent_date}")
            if metadata:
                yield "\n".join(metadata)
            if msg.body:
                yield msg.body.strip()

            for attachment in msg.attachments:
                if attachment.Filename:
                    yield f"\nAttachment: {attachment.Filename}"

        except Exception as e:
            raise ValueError(f"Error processing MSG file: {str(e)}") from e
        finally:
            os.remove(tmp_file.name)
