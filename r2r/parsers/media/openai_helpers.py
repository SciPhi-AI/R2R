"""Implementations of parsers for different data types."""

import requests


def process_frame_with_openai(
    data: bytes,
    api_key: str,
    model: str = "gpt-4o",
    max_tokens: int = 2_048,
    api_base: str = "https://api.openai.com/v1/chat/completions",
) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "First, provide a title for the image, then explain everything that you see. Be very thorough in your analysis as a user will need to understand the image without seeing it. If it is possible to transcribe the image to text directly, then do so. The more detail you provide, the better the user will understand the image.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
                    },
                ],
            }
        ],
        "max_tokens": max_tokens,
    }

    response = requests.post(api_base, headers=headers, json=payload)
    response_json = response.json()
    return response_json["choices"][0]["message"]["content"]


def process_audio_with_openai(
    audio_file,
    api_key: str,
    audio_api_base: str = "https://api.openai.com/v1/audio/transcriptions",
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}

    transcription_response = requests.post(
        audio_api_base,
        headers=headers,
        files={"file": audio_file},
        data={"model": "whisper-1"},
    )
    transcription = transcription_response.json()

    return transcription["text"]
