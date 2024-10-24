import asyncio
import contextlib

import pytest

from core import CompletionConfig, GenerationConfig
from core.providers import LiteLLMCompletionProvider


def test_litellm_initialization(litellm_completion_provider):
    assert isinstance(litellm_completion_provider, LiteLLMCompletionProvider)


def test_litellm_invalid_provider_initialization():
    with pytest.raises(ValueError):
        config = CompletionConfig(provider="invalid_provider")
        LiteLLMCompletionProvider(config)


@pytest.mark.asyncio
async def test_litellm_async_completion(litellm_completion_provider):
    generation_config = GenerationConfig(model="gpt-3.5-turbo")
    messages = [{"role": "user", "content": "Hello!"}]

    with contextlib.suppress(asyncio.CancelledError):
        response = await litellm_completion_provider.aget_completion(
            messages, generation_config
        )
    assert len(response.choices) > 0
