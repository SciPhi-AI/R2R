import base64
import os
from typing import AsyncGenerator

from core.base.parsers.base_parser import AsyncParser
from core.parsers.media.openai_helpers import (
    process_audio_with_openai,
    process_frame_with_openai,
)


class MovieParser(AsyncParser):
    """A parser for movie data."""

    def __init__(
        self,
        model: str = "gpt-4o",
        max_tokens: int = 2048,
        seconds_per_frame: int = 2,
        max_frames: int = 10,
    ):
        try:
            import cv2

            self.cv2 = cv2
        except ImportError:
            raise ValueError(
                "Error, `opencv-python` is required to run `MovieParser`. Please install it using `pip install opencv-python`."
            )
        try:
            import moviepy.editor as mp

            self.mp = mp
        except ImportError:
            raise ValueError(
                "Error, `moviepy` is required to run `MovieParser`. Please install it using `pip install moviepy`."
            )

        self.model = model
        self.max_tokens = max_tokens
        self.seconds_per_frame = seconds_per_frame
        self.max_frames = max_frames
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError(
                "Error, environment variable `OPENAI_API_KEY` is required to run `MovieParser`."
            )

    async def ingest(
        self, data: bytes, chunk_size: int = 1024
    ) -> AsyncGenerator[str, None]:
        """Ingest movie data and yield a description."""
        temp_video_path = "temp_movie.mp4"
        with open(temp_video_path, "wb") as f:
            f.write(data)
        try:
            raw_frames, audio_file = self.process_video(temp_video_path)
            for frame in raw_frames:
                frame_text = process_frame_with_openai(
                    frame, self.openai_api_key
                )
                yield frame_text

            if audio_file:
                transcription_text = process_audio_with_openai(
                    audio_file, self.openai_api_key
                )
                # split text into small chunks and yield them
                for i in range(0, len(transcription_text), chunk_size):
                    text = transcription_text[i : i + chunk_size]
                    if text and text != "":
                        yield text
        finally:
            os.remove(temp_video_path)

    def process_video(self, video_path):
        base64Frames = []
        base_video_path, _ = os.path.splitext(video_path)

        video = self.cv2.VideoCapture(video_path)
        total_frames = int(video.get(self.cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(self.cv2.CAP_PROP_FPS)
        frames_to_skip = int(fps * self.seconds_per_frame)
        curr_frame = 0

        # Calculate frames to skip based on max_frames if it is set
        if self.max_frames and self.max_frames < total_frames / frames_to_skip:
            frames_to_skip = max(total_frames // self.max_frames, 1)

        frame_count = 0
        while curr_frame < total_frames - 1 and (
            not self.max_frames or frame_count < self.max_frames
        ):
            video.set(self.cv2.CAP_PROP_POS_FRAMES, curr_frame)
            success, frame = video.read()
            if not success:
                break
            _, buffer = self.cv2.imencode(".jpg", frame)
            base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
            curr_frame += frames_to_skip
            frame_count += 1
        video.release()

        audio_path = f"{base_video_path}.wav"
        audio_file = None
        with self.mp.VideoFileClip(video_path) as clip:
            if clip.audio is not None:
                clip.audio.write_audiofile(
                    audio_path, codec="pcm_s16le", fps=16000
                )
                audio_file = open(audio_path, "rb")
                os.remove(audio_path)

        return base64Frames, audio_file
