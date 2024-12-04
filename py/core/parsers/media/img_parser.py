import base64
import logging
from typing import AsyncGenerator

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class ImageParser(AsyncParser[str | bytes]):
    """A parser for image data using vision models."""

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

        try:
            from litellm import supports_vision

            self.supports_vision = supports_vision
        except ImportError:
            logger.error("Failed to import LiteLLM vision support")
            raise ImportError(
                "Please install the `litellm` package to use the ImageParser."
            )

    async def ingest(  # type: ignore
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Ingest image data and yield a description using vision model.

        Args:
            data: Image data (bytes or base64 string)
            *args, **kwargs: Additional arguments passed to the completion call

        Yields:
            Chunks of image description text
        """
        if not self.vision_prompt_text:
            self.vision_prompt_text = await self.database_provider.get_cached_prompt(  # type: ignore
                prompt_name=self.config.vision_img_prompt_name
            )
        try:
            # Verify model supports vision
            if not self.supports_vision(model=self.config.vision_img_model):
                raise ValueError(
                    f"Model {self.config.vision_img_model} does not support vision"
                )

            # Encode image data if needed
            if isinstance(data, bytes):
                image_data = base64.b64encode(data).decode("utf-8")
            else:
                image_data = data

            # Configure the generation parameters
            generation_config = GenerationConfig(
                model=self.config.vision_img_model,
                stream=False,
            )

            # Prepare message with image
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
