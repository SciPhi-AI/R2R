import asyncio
import contextlib

import pytest

from core import EmbeddingConfig
from core.providers import LiteLLMEmbeddingProvider


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture
def litellm_provider(app_config):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="openai/text-embedding-3-small",
        base_dimension=1536,
        app=app_config
    )

    return LiteLLMEmbeddingProvider(config)


def test_litellm_initialization(litellm_provider):
    assert isinstance(litellm_provider, LiteLLMEmbeddingProvider)
    assert litellm_provider.base_model == "openai/text-embedding-3-small"
    assert litellm_provider.base_dimension == 1536


def test_litellm_invalid_provider_initialization(app_config):
    with pytest.raises(ValueError):
        config = EmbeddingConfig(provider="invalid_provider", app=app_config)
        LiteLLMEmbeddingProvider(config)


def test_litellm_get_embedding(litellm_provider):
    embedding = litellm_provider.get_embedding("test text")
    assert len(embedding) == 1536
    assert isinstance(embedding, list)


@pytest.mark.asyncio
async def test_litellm_async_get_embedding(litellm_provider):
    with contextlib.suppress(asyncio.CancelledError):
        embedding = await litellm_provider.async_get_embedding("test text")
        assert len(embedding) == 1536
        assert isinstance(embedding, list)


def test_litellm_get_embeddings(litellm_provider):
    embeddings = litellm_provider.get_embeddings(["text1", "text2"])
    assert len(embeddings) == 2
    assert all(len(emb) == 1536 for emb in embeddings)


@pytest.mark.asyncio
async def test_litellm_async_get_embeddings(litellm_provider):
    with contextlib.suppress(asyncio.CancelledError):
        embeddings = await litellm_provider.async_get_embeddings(
            ["text1", "text2"]
        )
        assert len(embeddings) == 2
        assert all(len(emb) == 1536 for emb in embeddings)


def test_litellm_rerank_model_not_supported(app_config):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="openai/text-embedding-3-small",
        base_dimension=1536,
        rerank_model="some-model",
        app=app_config
    )
    with pytest.raises(
        ValueError, match="does not support separate reranking"
    ):
        LiteLLMEmbeddingProvider(config)


def test_litellm_unsupported_stage(app_config):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="openai/text-embedding-3-small",
        base_dimension=1536,
        app=app_config
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        ValueError, match="LiteLLMEmbeddingProvider only supports search stage"
    ):
        provider.get_embedding(
            "test", stage=LiteLLMEmbeddingProvider.PipeStage.RERANK
        )


@pytest.mark.asyncio
async def test_litellm_async_unsupported_stage(app_config):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="openai/text-embedding-3-small",
        base_dimension=1536,
        app=app_config
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        ValueError, match="LiteLLMEmbeddingProvider only supports search stage"
    ):
        await provider.async_get_embedding(
            "test", stage=LiteLLMEmbeddingProvider.PipeStage.RERANK
        )


def test_litellm_get_embedding_error(mocker, litellm_provider):
    mocker.patch.object(
        litellm_provider, "get_embedding", side_effect=Exception("Test error")
    )
    with pytest.raises(Exception, match="Test error"):
        litellm_provider.get_embedding("test")


@pytest.mark.asyncio
async def test_litellm_async_get_embedding_error(mocker, litellm_provider):
    mocker.patch.object(
        litellm_provider,
        "async_get_embedding",
        side_effect=Exception("Test error"),
    )
    with pytest.raises(Exception, match="Test error"):
        await litellm_provider.async_get_embedding("test")
