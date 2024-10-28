import base64
import logging
from typing import AsyncGenerator

from core.base.abstractions import DataType, GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class ImageParser(AsyncParser[DataType]):
    """A parser for image data using vision models."""

    DEFAULT_VISION_PROMPT = "First, provide a title for the image, then explain everything that you see. Be very thorough in your analysis as a user will need to understand the image without seeing it. If it is possible to transcribe the image to text directly, then do so. The more detail you provide, the better the user will understand the image."

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        try:
            from litellm import supports_vision

            self.supports_vision = supports_vision
        except ImportError:
            logger.error("Failed to import LiteLLM vision support")
            raise ImportError(
                "Please install the `litellm` package to use the ImageParser."
            )

    async def ingest(  # type: ignore
        self, data: DataType, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Ingest image data and yield a description using vision model.

        Args:
            data: Image data (bytes or base64 string)
            chunk_size: Size of text chunks to yield
            *args, **kwargs: Additional arguments passed to the completion call

        Yields:
            Chunks of image description text
        """
        try:
            # Verify model supports vision
            if not self.supports_vision(model=self.config.vision_model):
                raise ValueError(
                    f"Model {self.config.vision_model} does not support vision"
                )

            # Encode image data if needed
            if isinstance(data, bytes):
                image_data = base64.b64encode(data).decode("utf-8")
            else:
                image_data = data

            # Configure the generation parameters
            generation_config = GenerationConfig(
                model=self.config.vision_model,
                stream=False,
            )

            # Prepare message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.config.vision_prompt
                            or self.DEFAULT_VISION_PROMPT,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            ]

            # Get completion from LiteLLM provider
            response = await self.llm_provider.aget_completion(
                messages=messages, generation_config=generation_config
            )

            # Extract description from response
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
