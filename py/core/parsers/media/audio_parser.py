# type: ignore
import logging
import os
import tempfile
from typing import AsyncGenerator

from litellm import atranscription

from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class AudioParser(AsyncParser[bytes]):
    """A parser for audio data using Whisper transcription."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.atranscription = atranscription

    async def ingest(  # type: ignore
        self, data: bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest audio data and yield a transcription using Whisper via
        LiteLLM.

        Args:
            data: Raw audio bytes
            *args, **kwargs: Additional arguments passed to the transcription call

        Yields:
            Chunks of transcribed text
        """
        try:
            # Create a temporary file to store the audio data
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name

            # Call Whisper transcription
            response = await self.atranscription(
                model=self.config.audio_transcription_model
                or self.config.app.audio_lm,
                file=open(temp_file_path, "rb"),
                **kwargs,
            )

            # The response should contain the transcribed text directly
            yield response.text

        except Exception as e:
            logger.error(f"Error processing audio with Whisper: {str(e)}")
            raise

        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")
