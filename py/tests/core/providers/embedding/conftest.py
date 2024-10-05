import asyncio

import pytest

from core import EmbeddingConfig
from core.providers import OllamaEmbeddingProvider, OpenAIEmbeddingProvider


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
def openai_provider(app_config):
    config = EmbeddingConfig(
        provider="openai",
        base_model="text-embedding-ada-002",
        base_dimension=1536,
        app=app_config,
    )
    return OpenAIEmbeddingProvider(config)


@pytest.fixture
def ollama_provider(app_config):
    config = EmbeddingConfig(
        provider="ollama",
        base_model="mxbai-embed-large",
        base_dimension=1024,
        app=app_config,
    )
    return OllamaEmbeddingProvider(config)
