import os
from typing import AsyncGenerator

from r2r.base.parsers.base_parser import AsyncParser
from r2r.parsers.media.openai_helpers import process_audio_with_openai


class AudioParser(AsyncParser[bytes]):
    """A parser for audio data."""

    def __init__(
        self, api_base: str = "https://api.openai.com/v1/audio/transcriptions"
    ):
        self.api_base = api_base
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "Error, environment variable `OPENAI_API_KEY` is required to run `AudioParser`."
            )

    async def ingest(self, data: bytes) -> AsyncGenerator[str, None]:
        """Ingest audio data and yield a transcription."""
        temp_audio_path = "temp_audio.wav"
        with open(temp_audio_path, "wb") as f:
            f.write(data)
        try:
            transcription_text = process_audio_with_openai(
                open(temp_audio_path, "rb"), self.openai_api_key
            )
            yield transcription_text
        finally:
            os.remove(temp_audio_path)
