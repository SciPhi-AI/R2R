import base64
import logging
import os
from io import BytesIO
from typing import AsyncGenerator

from PIL import Image

from core.base.abstractions.document import DataType
from core.base.parsers.base_parser import AsyncParser
from core.parsers.media.openai_helpers import process_frame_with_openai
from core.telemetry.telemetry_decorator import telemetry_event

logger = logging.getLogger(__name__)


class ImageParser(AsyncParser[DataType]):
    """A parser for image data."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tokens: int = 2_048,
        api_base: str = "https://api.openai.com/v1/chat/completions",
        max_image_size: int = 1 * 1024 * 1024,  # 4MB limit
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.api_base = api_base
        self.max_image_size = max_image_size

    async def ingest(
        self, data: DataType, chunk_size: int = 1024
    ) -> AsyncGenerator[str, None]:
        """Ingest image data and yield a description."""

        if isinstance(data, bytes):
            # Encode to base64
            data = base64.b64encode(data).decode("utf-8")

        openai_text = process_frame_with_openai(
            data,
            self.openai_api_key,
            self.model,
            self.max_tokens,
            self.api_base,
        )

        # split text into small chunks and yield them
        for i in range(0, len(openai_text), chunk_size):
            text = openai_text[i : i + chunk_size]
            if text and text != "":
                yield text
