import os
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.parsers.media.openai_helpers import process_audio_with_openai


class AudioParser(AsyncParser[bytes]):
    """A parser for audio data."""

    def __init__(
        self, api_base: str = "https://api.openai.com/v1/audio/transcriptions"
    ):
        self.api_base = api_base
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")

    async def ingest(  # type: ignore
        self, data: bytes, chunk_size: int = 1024
    ) -> AsyncGenerator[str, None]:
        """Ingest audio data and yield a transcription."""
        temp_audio_path = "temp_audio.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(data)
        try:
            transcription_text = process_audio_with_openai(
                open(temp_audio_path, "rb"), self.openai_api_key  # type: ignore
            )

            # split text into small chunks and yield them
            for i in range(0, len(transcription_text), chunk_size):
                text = transcription_text[i : i + chunk_size]
                if text and text != "":
                    yield text
        finally:
            os.remove(temp_audio_path)
