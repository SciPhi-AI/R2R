import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import CompletionConfig, GenerationConfig
from core.base.abstractions.llm import (
    LLMChatCompletion,
    LLMChatCompletionChunk,
)
from core.providers import LiteCompletionProvider, OpenAICompletionProvider


class MockCompletionResponse:
    def __init__(self, content):
        self.id = "mock_id"
        self.created = int(time.time())
        self.model = "gpt-4o-mini"
        self.object = "chat.completion"
        self.choices = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ]

    def dict(self):
        return {
            "id": self.id,
            "created": self.created,
            "model": self.model,
            "object": self.object,
            "choices": self.choices,
        }


class MockStreamResponse:
    def __init__(self, content):
        self.id = "mock_id"
        self.created = int(time.time())
        self.model = "gpt-4o-mini"
        self.object = "chat.completion.chunk"
        self.choices = [
            {"index": 0, "delta": {"content": content}, "finish_reason": None}
        ]

    def dict(self):
        return {
            "id": self.id,
            "created": self.created,
            "model": self.model,
            "object": self.object,
            "choices": self.choices,
        }


@pytest.fixture
def lite_llm():
    config = CompletionConfig(provider="litellm")
    return LiteCompletionProvider(config)


@pytest.fixture
def openai_llm():
    config = CompletionConfig(provider="openai")
    return OpenAICompletionProvider(config)


@pytest.fixture
def messages():
    return [
        {
            "role": "user",
            "content": "This is a test, return only the word `True`",
        }
    ]


@pytest.fixture
def generation_config():
    return GenerationConfig(
        model="gpt-4o-mini",
        temperature=0.0,
        top_p=0.9,
        max_tokens_to_sample=50,
        stream=False,
    )


@pytest.mark.parametrize("llm_fixture", ["lite_llm", "openai_llm"])
def test_get_completion(request, llm_fixture, messages, generation_config):
    llm = request.getfixturevalue(llm_fixture)

    with patch.object(
        llm, "_execute_task_sync", return_value=MockCompletionResponse("True")
    ):
        completion = llm.get_completion(messages, generation_config)
        assert isinstance(completion, LLMChatCompletion)
        assert completion.choices[0].message.role == "assistant"
        assert completion.choices[0].message.content.strip() == "True"
        assert completion.id == "mock_id"
        assert completion.model == "gpt-4o-mini"
        assert completion.object == "chat.completion"


@pytest.mark.parametrize("llm_fixture", ["lite_llm", "openai_llm"])
def test_get_completion_stream(
    request, llm_fixture, messages, generation_config
):
    llm = request.getfixturevalue(llm_fixture)
    generation_config.stream = True

    mock_responses = [
        MockStreamResponse("T"),
        MockStreamResponse("ru"),
        MockStreamResponse("e"),
    ]
    with patch.object(llm, "_execute_task_sync", return_value=mock_responses):
        stream = llm.get_completion_stream(messages, generation_config)
        chunks = list(stream)
        assert all(
            isinstance(chunk, LLMChatCompletionChunk) for chunk in chunks
        )
        assert len(chunks) == 3
        assert (
            "".join(chunk.choices[0].delta.content for chunk in chunks)
            == "True"
        )
        assert all(chunk.object == "chat.completion.chunk" for chunk in chunks)


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_fixture", ["lite_llm", "openai_llm"])
async def test_aget_completion(
    request, llm_fixture, messages, generation_config
):
    llm = request.getfixturevalue(llm_fixture)

    with patch.object(
        llm,
        "_execute_task",
        AsyncMock(return_value=MockCompletionResponse("True")),
    ):
        completion = await llm.aget_completion(messages, generation_config)
        assert isinstance(completion, LLMChatCompletion)
        assert completion.choices[0].message.role == "assistant"
        assert completion.choices[0].message.content.strip() == "True"
        assert completion.id == "mock_id"
        assert completion.model == "gpt-4o-mini"
        assert completion.object == "chat.completion"


@pytest.mark.asyncio
@pytest.mark.parametrize("llm_fixture", ["lite_llm", "openai_llm"])
async def test_aget_completion_stream(
    request, llm_fixture, messages, generation_config
):
    llm = request.getfixturevalue(llm_fixture)
    generation_config.stream = True

    async def mock_stream():
        yield MockStreamResponse("T")
        yield MockStreamResponse("ru")
        yield MockStreamResponse("e")

    with patch.object(
        llm, "_execute_task", AsyncMock(return_value=mock_stream())
    ):
        stream = llm.aget_completion_stream(messages, generation_config)
        chunks = [chunk async for chunk in stream]
        assert all(
            isinstance(chunk, LLMChatCompletionChunk) for chunk in chunks
        )
        assert len(chunks) == 3
        assert (
            "".join(chunk.choices[0].delta.content for chunk in chunks)
            == "True"
        )
        assert all(chunk.object == "chat.completion.chunk" for chunk in chunks)
