# type: ignore
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)


class BMPParser(AsyncParser[str | bytes]):
    """A parser for BMP image data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config

        import struct

        self.struct = struct

    async def extract_bmp_metadata(self, data: bytes) -> dict:
        """Extract metadata from BMP file header."""
        try:
            # BMP header format
            header_format = "<2sIHHI"
            header_size = self.struct.calcsize(header_format)

            # Unpack header data
            (
                signature,
                file_size,
                reserved,
                reserved2,
                data_offset,
            ) = self.struct.unpack(header_format, data[:header_size])

            # DIB header
            dib_format = "<IiiHHIIiiII"
            dib_size = self.struct.calcsize(dib_format)
            dib_data = self.struct.unpack(dib_format, data[14 : 14 + dib_size])

            width = dib_data[1]
            height = abs(dib_data[2])  # Height can be negative
            bits_per_pixel = dib_data[4]
            compression = dib_data[5]

            return {
                "width": width,
                "height": height,
                "bits_per_pixel": bits_per_pixel,
                "file_size": file_size,
                "compression": compression,
            }
        except Exception as e:
            return {"error": f"Failed to parse BMP header: {str(e)}"}

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest BMP data and yield metadata description."""
        if isinstance(data, str):
            # Convert base64 string to bytes if needed
            import base64

            data = base64.b64decode(data)

        metadata = await self.extract_bmp_metadata(data)

        # Generate description of the BMP file
        yield f"BMP image with dimensions {metadata.get('width', 'unknown')}x{metadata.get('height', 'unknown')} pixels, {metadata.get('bits_per_pixel', 'unknown')} bits per pixel, file size: {metadata.get('file_size', 'unknown')} bytes"
