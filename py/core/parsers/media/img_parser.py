# type: ignore
import base64
import logging
from io import BytesIO
from typing import AsyncGenerator

import pillow_heif
from PIL import Image

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class ImageParser(AsyncParser[str | bytes]):
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
        self.pillow_heif = pillow_heif
        self.pillow_heif.register_heif_opener()

    def _is_heic(self, data: bytes) -> bool:
        """More robust HEIC detection using magic numbers and patterns."""
        heic_patterns = [
            b"ftyp",
            b"heic",
            b"heix",
            b"hevc",
            b"HEIC",
            b"mif1",
            b"msf1",
            b"hevc",
            b"hevx",
        ]

        # Check for HEIC file signature
        try:
            header = data[:32]  # Get first 32 bytes
            return any(pattern in header for pattern in heic_patterns)
        except Exception as e:
            logger.error(f"Error checking for HEIC format: {str(e)}")
            return False

    async def _convert_heic_to_jpeg(self, data: bytes) -> bytes:
        """Convert HEIC image to JPEG format."""
        try:
            # Create BytesIO object for input
            input_buffer = BytesIO(data)

            # Load HEIC image using pillow_heif
            heif_file = self.pillow_heif.read_heif(input_buffer)

            # Get the primary image - API changed, need to get first image
            heif_image = heif_file[0]  # Get first image in the container

            # Convert to PIL Image directly from the HEIF image
            pil_image = heif_image.to_pillow()

            # Convert to RGB if needed
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")

            # Save as JPEG
            output_buffer = BytesIO()
            pil_image.save(output_buffer, format="JPEG", quality=95)
            return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"Error converting HEIC to JPEG: {str(e)}")
            raise

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
            if isinstance(data, bytes):
                try:
                    # Check if it's HEIC and convert if necessary
                    if self._is_heic(data):
                        logger.debug(
                            "Detected HEIC format, converting to JPEG"
                        )
                        data = await self._convert_heic_to_jpeg(data)
                    image_data = base64.b64encode(data).decode("utf-8")
                except Exception as e:
                    logger.error(f"Error processing image data: {str(e)}")
                    raise
            else:
                image_data = data

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
            logger.error(f"Error processing image with vision model: {str(e)}")
            raise
