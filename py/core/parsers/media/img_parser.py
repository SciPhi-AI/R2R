import base64
import os
from io import BytesIO
from typing import AsyncGenerator

from PIL import Image

from core.base.abstractions.document import DataType
from core.base.parsers.base_parser import AsyncParser
from core.parsers.media.openai_helpers import process_frame_with_openai


class ImageParser(AsyncParser[DataType]):
    """A parser for image data."""

    def __init__(
        self,
        model: str = "gpt-4o",
        max_tokens: int = 2_048,
        api_base: str = "https://api.openai.com/v1/chat/completions",
        max_image_size: int = 1 * 1024 * 1024,  # 4MB limit
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "Error, environment variable `OPENAI_API_KEY` is required to run `ImageParser`."
            )
        self.api_base = api_base
        self.max_image_size = max_image_size

    def _resize_image(self, image_data: bytes, compression_ratio) -> bytes:
        img = Image.open(BytesIO(image_data))
        img_byte_arr = BytesIO()
        img.save(
            img_byte_arr, format="JPEG", quality=int(100 * compression_ratio)
        )
        return img_byte_arr.getvalue()

    async def ingest(self, data: DataType) -> AsyncGenerator[str, None]:
        """Ingest image data and yield a description."""
        if isinstance(data, bytes):
            # Resize the image if it's too large
            if len(data) > self.max_image_size:
                data = self._resize_image(
                    data, float(self.max_image_size) / len(data)
                )

            # Encode to base64
            data = base64.b64encode(data).decode("utf-8")

        yield process_frame_with_openai(
            data,
            self.openai_api_key,
            self.model,
            self.max_tokens,
            self.api_base,
        )
