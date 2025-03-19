import base64
import io
import logging
from typing import Tuple

from PIL import Image

logger = logging.getLogger()


def resize_base64_image(
    base64_string: str,
    max_size: Tuple[int, int] = (512, 512),
    max_megapixels: float = 0.25,
) -> str:
    """Aggressively resize images with better error handling and debug output"""
    logger.debug(
        f"RESIZING NOW!!! Original length: {len(base64_string)} chars"
    )

    # Decode base64 string to bytes
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        logger.debug(f"Image opened successfully: {image.format} {image.size}")
    except Exception as e:
        logger.debug(f"Failed to decode/open image: {e}")
        # Emergency fallback - truncate the base64 string to reduce tokens
        if len(base64_string) > 50000:
            return base64_string[:50000]
        return base64_string

    try:
        width, height = image.size
        current_megapixels = (width * height) / 1_000_000
        logger.debug(
            f"Original dimensions: {width}x{height} ({current_megapixels:.2f} MP)"
        )

        # MUCH more aggressive resizing for large images
        if current_megapixels > 0.5:
            max_size = (384, 384)
            max_megapixels = 0.15
            logger.debug("Large image detected! Using more aggressive limits")

        # Calculate new dimensions with strict enforcement
        # Always resize if the image is larger than we want
        scale_factor = min(
            max_size[0] / width,
            max_size[1] / height,
            (max_megapixels / current_megapixels) ** 0.5,
        )

        if scale_factor >= 1.0:
            # No resize needed, but still compress
            new_width, new_height = width, height
        else:
            # Apply scaling
            new_width = max(int(width * scale_factor), 64)  # Min width
            new_height = max(int(height * scale_factor), 64)  # Min height

        # Always resize/recompress the image
        logger.debug(f"Resizing to: {new_width}x{new_height}")
        resized_image = image.resize((new_width, new_height), Image.LANCZOS)  # type: ignore

        # Convert back to base64 with strong compression
        buffer = io.BytesIO()
        if image.format == "JPEG" or image.format is None:
            # Apply very aggressive JPEG compression
            quality = 50  # Very low quality to reduce size
            resized_image.save(
                buffer, format="JPEG", quality=quality, optimize=True
            )
        else:
            # For other formats
            resized_image.save(
                buffer, format=image.format or "PNG", optimize=True
            )

        resized_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.debug(
            f"Resized base64 length: {len(resized_base64)} chars (reduction: {100 * (1 - len(resized_base64) / len(base64_string)):.1f}%)"
        )
        return resized_base64

    except Exception as e:
        logger.debug(f"Error during resize: {e}")
        # If anything goes wrong, truncate the base64 to a reasonable size
        if len(base64_string) > 50000:
            return base64_string[:50000]
        return base64_string


def estimate_image_tokens(width: int, height: int) -> int:
    """
    Estimate the number of tokens an image will use based on Anthropic's formula.

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Estimated number of tokens
    """
    return int((width * height) / 750)
