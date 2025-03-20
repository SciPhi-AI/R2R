# type: ignore
import base64
import imghdr
import logging
from typing import AsyncGenerator, Optional

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
    # Mapping of file extensions to MIME types
    MIME_TYPE_MAPPING = {
        "bmp": "image/bmp",
        "gif": "image/gif",
        "heic": "image/heic",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "png": "image/png",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "webp": "image/webp",
    }

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
        """Detect HEIC format using magic numbers and patterns."""
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

        try:
            header = data[:32]  # Get first 32 bytes
            return any(pattern in header for pattern in heic_patterns)
        except Exception as e:
            logger.error(f"Error checking for HEIC format: {str(e)}")
            return False

    def _is_jpeg(self, data: bytes) -> bool:
        """Detect JPEG format using magic numbers."""
        return len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8

    def _is_png(self, data: bytes) -> bool:
        """Detect PNG format using magic numbers."""
        png_signature = b"\x89PNG\r\n\x1a\n"
        return data.startswith(png_signature)

    def _is_bmp(self, data: bytes) -> bool:
        """Detect BMP format using magic numbers."""
        return data.startswith(b"BM")

    def _is_tiff(self, data: bytes) -> bool:
        """Detect TIFF format using magic numbers."""
        return (
            data.startswith(b"II*\x00")  # Little-endian
            or data.startswith(b"MM\x00*")
        )  # Big-endian

    def _get_image_media_type(
        self, data: bytes, filename: Optional[str] = None
    ) -> str:
        """
        Determine the correct media type based on image data and/or filename.

        Args:
            data: The binary image data
            filename: Optional filename which may contain extension information

        Returns:
            str: The MIME type for the image
        """
        try:
            # First, try format-specific detection functions
            if self._is_heic(data):
                return "image/heic"
            if self._is_jpeg(data):
                return "image/jpeg"
            if self._is_png(data):
                return "image/png"
            if self._is_bmp(data):
                return "image/bmp"
            if self._is_tiff(data):
                return "image/tiff"

            # Try using imghdr as a fallback
            img_type = imghdr.what(None, h=data)
            if img_type:
                # Map the detected type to a MIME type
                return self.MIME_TYPE_MAPPING.get(
                    img_type, f"image/{img_type}"
                )

            # If we have a filename, try to get the type from the extension
            if filename:
                extension = filename.split(".")[-1].lower()
                if extension in self.MIME_TYPE_MAPPING:
                    return self.MIME_TYPE_MAPPING[extension]

            # If all else fails, default to octet-stream (generic binary)
            logger.warning(
                "Could not determine image type, using application/octet-stream"
            )
            return "application/octet-stream"

        except Exception as e:
            logger.error(f"Error determining image media type: {str(e)}")
            return "application/octet-stream"  # Default to generic binary as fallback

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
            filename = kwargs.get("filename", None)

            if isinstance(data, bytes):
                try:
                    # Detect image type from binary data and filename (if available)
                    media_type = self._get_image_media_type(data, filename)
                    logger.info(f"Detected image type: {media_type}")

                    # We keep the original image data as-is, without conversion to JPEG
                    image_data = base64.b64encode(data).decode("utf-8")

                except Exception as e:
                    logger.error(f"Error processing image data: {str(e)}")
                    raise
            else:
                # If data is already a string (base64), we assume it has a reliable content type
                # from the source that encoded it
                image_data = data

                # Try to determine the media type from the context if available
                media_type = kwargs.get(
                    "media_type", "application/octet-stream"
                )

            model = (
                kwargs.get("vlm", None)
                or self.config.app.vlm
            )

            generation_config = GenerationConfig(
                model=model,
                stream=False,
            )

            if "anthropic" in model:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.vision_prompt_text},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                        ],
                    }
                ]
            else:
                # For OpenAI-style APIs, use their format
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.vision_prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_data}"
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