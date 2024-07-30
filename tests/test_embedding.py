import asyncio
from unittest.mock import patch

import pytest

from r2r import EmbeddingConfig


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


from r2r.providers import LiteLLMEmbeddingProvider


@pytest.fixture
def litellm_provider():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    return LiteLLMEmbeddingProvider(config)


def test_litellm_initialization(litellm_provider):
    assert isinstance(litellm_provider, LiteLLMEmbeddingProvider)
    assert litellm_provider.base_model == "text-embedding-3-small"
    assert litellm_provider.base_dimension == 1536


def test_litellm_invalid_provider_initialization():
    config = EmbeddingConfig(provider="invalid_provider")
    with pytest.raises(ValueError):
        LiteLLMEmbeddingProvider(config)


def test_litellm_get_embedding(litellm_provider):
    embedding = litellm_provider.get_embedding("test text")
    assert len(embedding) == 1536
    assert isinstance(embedding, list)


@pytest.mark.asyncio
async def test_litellm_async_get_embedding(litellm_provider):
    try:
        embedding = await litellm_provider.async_get_embedding("test text")
        assert len(embedding) == 1536
        assert isinstance(embedding, list)
    except asyncio.CancelledError:
        pass  # Task cancelled as expected


def test_litellm_get_embeddings(litellm_provider):
    embeddings = litellm_provider.get_embeddings(["text1", "text2"])
    assert len(embeddings) == 2
    assert all(len(emb) == 1536 for emb in embeddings)


@pytest.mark.asyncio
async def test_litellm_async_get_embeddings(litellm_provider):
    try:
        embeddings = await litellm_provider.async_get_embeddings(
            ["text1", "text2"]
        )
        assert len(embeddings) == 2
        assert all(len(emb) == 1536 for emb in embeddings)
    except asyncio.CancelledError:
        pass  # Task cancelled as expected


def test_litellm_missing_provider():
    config = EmbeddingConfig()
    with pytest.raises(ValueError, match="Must set provider"):
        LiteLLMEmbeddingProvider(config)


def test_litellm_incorrect_provider():
    config = EmbeddingConfig(provider="not_litellm")
    with pytest.raises(
        ValueError, match="Provider 'not_litellm' is not supported"
    ):
        LiteLLMEmbeddingProvider(config)


def test_litellm_rerank_model_not_supported():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
        rerank_model="some-model",
    )
    with pytest.raises(
        ValueError, match="does not support separate reranking"
    ):
        LiteLLMEmbeddingProvider(config)


def test_litellm_unsupported_stage():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        ValueError, match="LiteLLMEmbeddingProvider only supports search stage"
    ):
        provider.get_embedding(
            "test", stage=LiteLLMEmbeddingProvider.PipeStage.RERANK
        )


@pytest.mark.asyncio
async def test_litellm_async_unsupported_stage():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        ValueError, match="LiteLLMEmbeddingProvider only supports search stage"
    ):
        await provider.async_get_embedding(
            "test", stage=LiteLLMEmbeddingProvider.PipeStage.RERANK
        )


def test_litellm_tokenize_string_not_implemented():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        NotImplementedError,
        match="Tokenization is not supported by LiteLLMEmbeddingProvider",
    ):
        provider.tokenize_string(
            "test",
            "text-embedding-3-small",
            LiteLLMEmbeddingProvider.PipeStage.BASE,
        )


@pytest.mark.asyncio
async def test_litellm_async_get_embeddings_unsupported_stage():
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    with pytest.raises(
        ValueError, match="LiteLLMEmbeddingProvider only supports search stage"
    ):
        await provider.async_get_embeddings(
            ["test1", "test2"], stage=LiteLLMEmbeddingProvider.PipeStage.RERANK
        )


# You might also want to test error handling in get_embedding and get_embeddings
def test_litellm_get_embedding_error_handling(mocker):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    mocker.patch.object(
        provider, "litellm_embedding", side_effect=Exception("Test error")
    )
    with pytest.raises(Exception, match="Test error"):
        provider.get_embedding("test")


@pytest.mark.asyncio
async def test_litellm_async_get_embedding_error_handling(mocker):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    provider = LiteLLMEmbeddingProvider(config)
    mocker.patch.object(
        provider, "litellm_aembedding", side_effect=Exception("Test error")
    )
    with pytest.raises(Exception, match="Test error"):
        await provider.async_get_embedding("test")


from r2r.providers import OpenAIEmbeddingProvider


@pytest.fixture
def openai_provider():
    config = EmbeddingConfig(
        provider="openai",
        base_model="text-embedding-3-small",
        base_dimension=1536,
    )
    return OpenAIEmbeddingProvider(config)


def test_openai_initialization(openai_provider):
    assert isinstance(openai_provider, OpenAIEmbeddingProvider)
    assert openai_provider.base_model == "text-embedding-3-small"
    assert openai_provider.base_dimension == 1536


def test_openai_invalid_provider_initialization():
    config = EmbeddingConfig(provider="invalid_provider")
    with pytest.raises(ValueError):
        OpenAIEmbeddingProvider(config)


def test_openai_get_embedding(openai_provider):
    embedding = openai_provider.get_embedding("test text")
    assert len(embedding) == 1536
    assert isinstance(embedding, list)


@pytest.mark.asyncio
async def test_openai_async_get_embedding(openai_provider):
    try:
        embedding = await openai_provider.async_get_embedding("test text")
        assert len(embedding) == 1536
        assert isinstance(embedding, list)
    except asyncio.CancelledError:
        pass  # Task cancelled as expected


def test_openai_get_embeddings(openai_provider):
    embeddings = openai_provider.get_embeddings(["text1", "text2"])
    assert len(embeddings) == 2
    assert all(len(emb) == 1536 for emb in embeddings)


@pytest.mark.asyncio
async def test_openai_async_get_embeddings(openai_provider):
    try:
        embeddings = await openai_provider.async_get_embeddings(
            ["text1", "text2"]
        )
        assert len(embeddings) == 2
        assert all(len(emb) == 1536 for emb in embeddings)
    except asyncio.CancelledError:
        pass  # Task cancelled as expected


def test_openai_tokenize_string(openai_provider):
    tokens = openai_provider.tokenize_string(
        "test text", "text-embedding-3-small"
    )
    assert isinstance(tokens, list)
    assert all(isinstance(token, int) for token in tokens)


def test_openai_missing_provider():
    config = EmbeddingConfig()
    with pytest.raises(ValueError, match="Must set provider"):
        OpenAIEmbeddingProvider(config)


def test_openai_incorrect_provider():
    config = EmbeddingConfig(provider="not_openai")
    with pytest.raises(
        ValueError, match="Provider 'not_openai' is not supported"
    ):
        OpenAIEmbeddingProvider(config)


def test_openai_unsupported_model():
    config = EmbeddingConfig(
        provider="openai", base_model="unsupported-model", base_dimension=1536
    )
    with pytest.raises(ValueError, match="embedding model .* not supported"):
        OpenAIEmbeddingProvider(config)


def test_openai_wrong_dimension():
    config = EmbeddingConfig(
        provider="openai",
        base_model="text-embedding-3-small",
        base_dimension=2048,
    )
    with pytest.raises(ValueError, match="Dimensions .* are not supported"):
        OpenAIEmbeddingProvider(config)


def test_openai_missing_model_or_dimension():
    config = EmbeddingConfig(provider="openai")
    with pytest.raises(
        ValueError,
        match="Must set base_model in order to initialize OpenAIEmbeddingProvider.",
    ):
        OpenAIEmbeddingProvider(config)


def test_openai_rerank_model_not_supported():
    config = EmbeddingConfig(
        provider="openai",
        base_model="text-embedding-3-small",
        base_dimension=1536,
        rerank_model="some-model",
    )
    with pytest.raises(
        ValueError, match="does not support separate reranking"
    ):
        OpenAIEmbeddingProvider(config)


from r2r.providers import OllamaEmbeddingProvider


@pytest.fixture
def ollama_provider():
    config = EmbeddingConfig(
        provider="ollama",
        base_model="mxbai-embed-large",
        base_dimension=1024,
    )
    return OllamaEmbeddingProvider(config)


def test_ollama_initialization(ollama_provider):
    assert isinstance(ollama_provider, OllamaEmbeddingProvider)
    assert ollama_provider.base_model == "mxbai-embed-large"
    assert ollama_provider.base_dimension == 1024


def test_ollama_invalid_provider_initialization():
    config = EmbeddingConfig(provider="invalid_provider")
    with pytest.raises(ValueError):
        OllamaEmbeddingProvider(config)


# from r2r.providers import SentenceTransformerEmbeddingProvider

# @pytest.fixture
# def sentence_transformer_provider():
#     config = EmbeddingConfig(
#         provider="sentence-transformers",
#         base_model="mixedbread-ai/mxbai-embed-large-v1",
#         base_dimension=512,
#         rerank_model="jinaai/jina-reranker-v1-turbo-en",
#         rerank_dimension=384,
#     )
#     return SentenceTransformerEmbeddingProvider(config)

# class FakeEmbedding:
#     def tolist(self):
#         return [[]]


# class FakeEncoder:
#     def encode(self, *args, **kwargs):
#         self._last_encode_args = args
#         self._last_encode_kwargs = kwargs
#         return FakeEmbedding()

# def test_sentence_transformer_indexing_no_prefix(sentence_transformer_provider):
#     encoder = FakeEncoder()
#     sentence_transformer_provider.search_encoder = encoder
#     embedding = sentence_transformer_provider.get_embedding("test text")
#     assert encoder._last_encode_args[0][0] == 'test text'


# def test_sentence_transformer_querying_with_prefix(sentence_transformer_provider):
#     from r2r.base import EmbeddingPurpose
#     encoder = FakeEncoder()
#     sentence_transformer_provider.search_encoder = encoder
#     embedding = sentence_transformer_provider.get_embedding("test text", purpose=EmbeddingPurpose.QUERY)
#     assert encoder._last_encode_args[0][0] == 'Represent this sentence for searching relevant passages: test text'


# def test_sentence_transformer_initialization(sentence_transformer_provider):
#     assert isinstance(
#         sentence_transformer_provider, SentenceTransformerEmbeddingProvider
#     )
#     assert sentence_transformer_provider.do_search
#     # assert sentence_transformer_provider.do_rerank


# def test_sentence_transformer_invalid_provider_initialization():
#     config = EmbeddingConfig(provider="invalid_provider")
#     with pytest.raises(ValueError):
#         SentenceTransformerEmbeddingProvider(config)


# def test_sentence_transformer_get_embedding(sentence_transformer_provider):
#     embedding = sentence_transformer_provider.get_embedding("test text")
#     assert len(embedding) == 512
#     assert isinstance(embedding, list)


# def test_sentence_transformer_get_embeddings(sentence_transformer_provider):
#     embeddings = sentence_transformer_provider.get_embeddings(
#         ["text1", "text2"]
#     )
#     assert len(embeddings) == 2
#     assert all(len(emb) == 512 for emb in embeddings)


# def test_sentence_transformer_rerank(sentence_transformer_provider):
#     results = [
#         VectorSearchResult(
#             id=generate_id_from_label("x"),
#             score=0.9,
#             metadata={"text": "doc1"},
#         ),
#         VectorSearchResult(
#             id=generate_id_from_label("y"),
#             score=0.8,
#             metadata={"text": "doc2"},
#         ),
#     ]
#     reranked_results = sentence_transformer_provider.rerank("query", results)
#     assert len(reranked_results) == 2
#     assert reranked_results[0].metadata["text"] == "doc1"
#     assert reranked_results[1].metadata["text"] == "doc2"


# def test_sentence_transformer_tokenize_string(sentence_transformer_provider):
#     with pytest.raises(ValueError):
#         sentence_transformer_provider.tokenize_string("test text")
