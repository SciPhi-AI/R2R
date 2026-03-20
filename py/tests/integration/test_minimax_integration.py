"""Integration tests for MiniMax LLM provider.

These tests require a valid MINIMAX_API_KEY environment variable.
They make real API calls to the MiniMax API.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set",
)


@pytest.fixture
def minimax_provider():
    """Create an OpenAICompletionProvider with MiniMax credentials."""
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {"MINIMAX_API_KEY": os.environ.get("MINIMAX_API_KEY", "")},
        clear=False,
    ):
        from core.base.providers.llm import CompletionConfig
        from core.providers.llm.openai import OpenAICompletionProvider

        config = CompletionConfig(provider="openai")
        return OpenAICompletionProvider(config)


@pytest.mark.asyncio
async def test_minimax_async_completion(minimax_provider):
    """Test basic async completion with MiniMax M2.7."""
    from core.base.abstractions import GenerationConfig

    gen_config = GenerationConfig(
        model="minimax/MiniMax-M2.7",
        temperature=0.1,
        max_tokens_to_sample=64,
    )
    messages = [{"role": "user", "content": "Say hello in one word."}]

    response = await minimax_provider.aget_completion(
        messages=messages,
        generation_config=gen_config,
    )
    assert response is not None
    assert len(response.choices) > 0
    assert response.choices[0].message.content is not None
    assert len(response.choices[0].message.content) > 0


@pytest.mark.asyncio
async def test_minimax_streaming(minimax_provider):
    """Test streaming completion with MiniMax M2.7."""
    from core.base.abstractions import GenerationConfig

    gen_config = GenerationConfig(
        model="minimax/MiniMax-M2.7",
        temperature=0.1,
        max_tokens_to_sample=32,
    )
    messages = [{"role": "user", "content": "Count to 3."}]

    chunks = []
    async for chunk in minimax_provider.aget_completion_stream(
        messages=messages,
        generation_config=gen_config,
    ):
        chunks.append(chunk)

    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_minimax_json_mode(minimax_provider):
    """Test JSON response format with MiniMax M2.5-highspeed (no thinking tags)."""
    import json
    import re

    from core.base.abstractions import GenerationConfig

    gen_config = GenerationConfig(
        model="minimax/MiniMax-M2.5-highspeed",
        temperature=0.1,
        max_tokens_to_sample=512,
        response_format={"type": "json_object"},
    )
    messages = [
        {
            "role": "user",
            "content": 'Return a JSON object with a single key "greeting" and value "hello".',
        }
    ]

    response = await minimax_provider.aget_completion(
        messages=messages,
        generation_config=gen_config,
    )
    content = response.choices[0].message.content
    assert content is not None
    # Strip any <think>...</think> tags that some models may include
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    data = json.loads(content)
    assert "greeting" in data
