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

logger = logging.getLogger(__name__)


class VideoParser(AsyncParser[str | bytes]):
    """
    A parser for video files.
    """

    # Mapping of file extensions to MIME types
    MIME_TYPE_MAPPING = {
        "mp4": "video/mp4",
        "avi": "video/avi",
        "mov": "video/quicktime",
        "mkv": "video/x-matroska",
    }

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        super().__init__()

        self.config = config
        self.database_provider = database_provider
        self.llm_provider = llm_provider

        self.vlm = (
            self.config.vlm or self.config.app.vlm if self.config.app else None
        )
        self.video_prompt_name = "video_understanding"
        self.video_prompt_args: dict = {}

        logger.info(
            "Video parser initialized with default prompt template: %s and vlm: %s",
            self.video_prompt_name,
            self.vlm,
        )

    async def ingest(  # type: ignore[override]
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Process video file for ingestion.

        Args:
            data: The video data to process, file url or raw bytes.
            **kwargs: Additional arguments:
                - file_type: The type of the video file (e.g., "mp4", "avi").
                - bytes_limit: Optional limit for raw bytes size.
                - vlm: Optional vision model to use for processing.
                - prompt_name: Optional name of the prompt template to use.
                - input_args: Optional arguments for the prompt template.

        Yields:
            str: Generated descriptions from video and audio analysis
        """
        extra_fields = kwargs.get("extra_fields", {})
        file_type = extra_fields.get("file_type")
        if not file_type:
            raise ValueError("file_type must be provided")
        if file_type not in self.MIME_TYPE_MAPPING:
            raise ValueError(
                f"file type must be one of {list(self.MIME_TYPE_MAPPING.keys())}"
            )
        bytes_limit = extra_fields.get(
            "bytes_limit", 5 * 1024 * 1024
        )  # Default to 5MB
        if not isinstance(bytes_limit, int):
            raise ValueError("bytes_limit must be an integer")

        vlm = extra_fields.get("vlm")
        prompt_name = extra_fields.get("prompt_name")
        input_args = extra_fields.get("input_args")
        if isinstance(data, bytes):
            if (
                bytes_limit is None
                or bytes_limit < 0
                or bytes_limit > 5 * 1024 * 1024
            ):
                raise ValueError(
                    "bytes_limit must be a positive integer up to 5MB"
                )
            if len(data) > bytes_limit:
                raise ValueError(
                    f"file raw bytes size must be less than {bytes_limit} bytes"
                )

        if isinstance(data, str):
            url_or_base64 = data
        elif isinstance(data, bytes):
            base564str = base64.b64encode(data).decode("utf-8")
            url_or_base64 = f"data:video/{file_type};base64,{base564str}"

        model = vlm or self.vlm
        if not model:
            raise ValueError("Vision model (vlm) must be provided")
        generation_config = GenerationConfig(
            model=model,
            stream=False,
        )

        prompt_name = prompt_name or self.video_prompt_name
        prompt_args = input_args or self.video_prompt_args
        prompts_handler = (
            self.database_provider.prompts_handler
            if hasattr(self.database_provider, "prompts_handler")
            else None
        )
        if not prompts_handler:
            raise ValueError(
                "Prompts handler is not available in the provider"
            )
        video_prompt_text = await prompts_handler.get_cached_prompt(
            prompt_name=prompt_name,
            inputs=prompt_args,
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "video_url",
                        "video_url": {"url": url_or_base64},
                    },
                    {"type": "text", "text": video_prompt_text},
                ],
            }
        ]

        try:
            response = await self.llm_provider.aget_completion(
                messages=messages, generation_config=generation_config
            )

            if not response.choices or not response.choices[0].message:
                raise ValueError("No response content")

            content = response.choices[0].message.content
            if not content:
                raise ValueError("Response content is empty")

            yield content

        except Exception as e:
            logger.error(
                f"Error processing file {url_or_base64[:50]}: {str(e)}"
            )
            raise
