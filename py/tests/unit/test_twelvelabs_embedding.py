import os

import pytest

from core.base import AppConfig, EmbeddingConfig
from core.providers import TwelveLabsEmbeddingProvider

MARENGO_DIMENSION = 512


def _config(**overrides) -> EmbeddingConfig:
    base = {
        "app": AppConfig(project_name="test_project"),
        "provider": "twelvelabs",
        "base_model": "marengo3.0",
        "base_dimension": MARENGO_DIMENSION,
    }
    base.update(overrides)
    return EmbeddingConfig(**base)


def test_twelvelabs_is_supported_provider():
    # No network / no API key needed: config validation only.
    config = _config()
    assert "twelvelabs" in config.supported_providers
    config.validate_config()


def test_rejects_wrong_provider():
    config = _config(provider="twelvelabs")
    config.provider = "openai"
    with pytest.raises(ValueError):
        TwelveLabsEmbeddingProvider(config)


def test_rejects_separate_rerank_model():
    config = _config(rerank_model="some-reranker")
    os.environ.setdefault("TWELVELABS_API_KEY", "test-key")
    with pytest.raises(ValueError):
        TwelveLabsEmbeddingProvider(config)


@pytest.mark.skipif(
    not os.getenv("TWELVELABS_API_KEY"),
    reason="TWELVELABS_API_KEY not set; skipping live Marengo call.",
)
async def test_marengo_text_embedding_dimension():
    provider = TwelveLabsEmbeddingProvider(_config())
    embedding = await provider.async_get_embedding(
        "a red car driving on a highway"
    )
    assert isinstance(embedding, list)
    assert len(embedding) == MARENGO_DIMENSION
    assert all(isinstance(x, float) for x in embedding)
