# type: ignore
from email import message_from_bytes, policy
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class EMLParser(AsyncParser[str | bytes]):
    """Parser for EML (email) files."""

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
        """Ingest EML data and yield email content."""
        if isinstance(data, str):
            raise ValueError("EML data must be in bytes format.")

        # Parse email with policy for modern email handling
        email_message = message_from_bytes(data, policy=policy.default)

        # Extract and yield email metadata
        metadata = []
        if email_message["Subject"]:
            metadata.append(f"Subject: {email_message['Subject']}")
        if email_message["From"]:
            metadata.append(f"From: {email_message['From']}")
        if email_message["To"]:
            metadata.append(f"To: {email_message['To']}")
        if email_message["Date"]:
            metadata.append(f"Date: {email_message['Date']}")

        if metadata:
            yield "\n".join(metadata)

        # Extract and yield email body
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    text = part.get_content()
                    if text.strip():
                        yield text.strip()
                elif part.get_content_type() == "text/html":
                    # Could add HTML parsing here if needed
                    continue
        else:
            body = email_message.get_content()
            if body.strip():
                yield body.strip()
