# type: ignore
from typing import AsyncGenerator

from msg_parser import MsOxMessage

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class MSGParser(AsyncParser[str | bytes]):
    """Parser for MSG (Outlook Message) files."""

    def init(
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

        try:
            # MsOxMessage can be initialized with file_bytes
            msg = MsOxMessage(file_bytes=data)

            # Extract metadata
            metadata = []
            subject = msg.get_subject()
            if subject:
                metadata.append(f"Subject: {subject}")

            if sender := msg.get_sender():
                metadata.append(f"From: {sender}")

            if recipients := msg.get_recipients() or []:
                metadata.append(f"To: {', '.join(recipients)}")

            if sent_date := msg.get_sent_date():
                metadata.append(f"Date: {sent_date}")

            if metadata:
                yield "\n".join(metadata)

            if body := msg.body:
                yield body.strip()

            # Extract attachments
            for attach_name, _attach_data in (msg.attachments or {}).items():
                yield f"\nAttachment: {attach_name}"

        except Exception as e:
            raise ValueError(f"Error processing MSG file: {str(e)}") from e
