# type: ignore
import base64
import logging
from io import BytesIO
from typing import AsyncGenerator

from PIL import Image

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger(__name__)


class TIFFParser(AsyncParser[str | bytes]):
    """Parser for TIFF image files."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.vision_prompt_text = None
        self.Image = Image

    async def _convert_tiff_to_jpeg(self, data: bytes) -> bytes:
        """Convert TIFF image to JPEG format."""
        try:
            # Open TIFF image
            with BytesIO(data) as input_buffer:
                tiff_image = self.Image.open(input_buffer)

                # Convert to RGB if needed
                if tiff_image.mode not in ("RGB", "L"):
                    tiff_image = tiff_image.convert("RGB")

                # Save as JPEG
                output_buffer = BytesIO()
                tiff_image.save(output_buffer, format="JPEG", quality=95)
                return output_buffer.getvalue()
        except Exception as e:
            raise ValueError(f"Error converting TIFF to JPEG: {str(e)}") from e

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.vision_prompt_text:
            self.vision_prompt_text = (
                await self.database_provider.prompts_handler.get_cached_prompt(
                    prompt_name=self.config.vision_img_prompt_name
                )
            )

        try:
            # Convert TIFF to JPEG
            if isinstance(data, bytes):
                jpeg_data = await self._convert_tiff_to_jpeg(data)
                image_data = base64.b64encode(jpeg_data).decode("utf-8")
            else:
                image_data = data

            # Use vision model to analyze image
            generation_config = GenerationConfig(
                model=self.config.vision_img_model or self.config.app.vlm,
                stream=False,
            )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.vision_prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            ]

            response = await self.llm_provider.aget_completion(
                messages=messages, generation_config=generation_config
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("No content in response")
                yield content
            else:
                raise ValueError("No response content")

        except Exception as e:
            raise ValueError(f"Error processing TIFF file: {str(e)}") from e
