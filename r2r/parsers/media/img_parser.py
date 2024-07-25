import os
from typing import AsyncGenerator

from r2r.base.abstractions.document import DataType
from r2r.base.parsers.base_parser import AsyncParser
from r2r.parsers.media.openai_helpers import process_frame_with_openai


class ImageParser(AsyncParser[DataType]):
    """A parser for image data."""

    def __init__(
        self,
        model: str = "gpt-4o",
        max_tokens: int = 2_048,
        api_base: str = "https://api.openai.com/v1/chat/completions",
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "Error, environment variable `OPENAI_API_KEY` is required to run `ImageParser`."
            )
        self.api_base = api_base

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest image data and yield a description."""
        if isinstance(data, bytes):
            import base64

            data = base64.b64encode(data).decode("utf-8")

        yield process_frame_with_openai(
            data,
            self.openai_api_key,
            self.model,
            self.max_tokens,
            self.api_base,
        )


class ImageParserLocal(AsyncParser[DataType]):

    def __init__(self):
        pass
