import logging
from typing import AsyncGenerator

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)
from core.providers import PostgresDatabaseProvider

logger = logging.getLogger(__name__)


class VideoParser(AsyncParser[str | bytes | dict]):
    """
    Video parser that processes video files for ingestion.

    This parser handles:
    - Video content analysis using LLM
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
        """
        Initialize the video parser.

        Sets up providers and configurations needed for video processing.
        """
        super().__init__()

        self.config = config
        self.database_provider = database_provider
        self.llm_provider = llm_provider

        self.video_prompt_name = self.config.extra_fields.get(
            "extra_video_prompt_name", "vision_img"
        )
        self.video_prompt_args = self.config.extra_fields.get(
            "extra_video_prompt_args", {}
        )

        logger.info(
            "Video parser initialized with default prompt template: %s",
            self.video_prompt_name,
        )

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Process video file for ingestion.

        Args:
            data: The video data to process, str or dict containing the URL of the video file
                file_url: Optional URL of the video file
            **kwargs:
                file_url: Optional URL of the video file
                vlm: Optional model to use for processing
                prompt_name: Optional name of the prompt to use
                prompt_args: Optional arguments for the prompt

        Yields:
            str: Generated descriptions from video and audio analysis
        """
        file_url = kwargs.get("file_url")
        logger.debug("file for ingest: %s", file_url)
        if file_url is None:
            raise ValueError("file_url is required")

        # Process video chunks
        async for description in self._call_llm(file_url, **kwargs):
            yield description

    async def _call_llm(self, file_url, **kwargs) -> AsyncGenerator[str, None]:

        model = kwargs.get("vlm", self.config.vlm)
        generation_config = GenerationConfig(
            model=model,
            stream=False,
        )

        # Load prompt texts
        prompt_name = kwargs.get("prompt_name", self.video_prompt_name)
        prompt_args = kwargs.get("prompt_args", self.video_prompt_args)
        video_prompt_text = (
            await self.database_provider.prompts_handler.get_cached_prompt(
                prompt_name=prompt_name,
                inputs=prompt_args,
            )
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": video_prompt_text},
                    {
                        "type": "video_url",
                        "video_url": {"url": file_url},
                    },
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
                raise ValueError("Empty response content")

            yield content

        except Exception as e:
            logger.error(f"Error processing file {file_url}: {str(e)}")
            raise
