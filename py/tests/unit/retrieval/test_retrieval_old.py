from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

# Import your classes
# from your_module import RetrievalService, SearchSettings, R2RConfig, R2RProviders, ...
from core.base import EmbeddingPurpose, SearchSettings


@pytest.fixture
def mock_providers():
    """
    Return a fake R2RProviders object with all relevant sub-providers mocked.
    """

    class MockProviders:
        def __init__(self):
            # Mock the embedding provider
            self.completion_embedding = AsyncMock()
            self.completion_embedding.async_get_embedding = AsyncMock(
                return_value=[0.123] * 768  # pretend vector
            )
            self.completion_embedding.arerank = AsyncMock(return_value=[])

            # Mock the chunk search provider
            self.database = AsyncMock()
            self.database.chunks_handler.hybrid_search = AsyncMock(
                return_value=[]
            )
            self.database.chunks_handler.semantic_search = AsyncMock(
                return_value=[]
            )
            self.database.chunks_handler.full_text_search = AsyncMock(
                return_value=[]
            )

            # Mock the graph search
            self.database.graphs_handler.graph_search = AsyncMock(
                return_value=iter([])
            )

            # Optional: If you want to test agent logic, mock those too
            self.llm = AsyncMock()
            self.llm.aget_completion = AsyncMock()
            self.llm.aget_completion_stream = AsyncMock()

            self.database.prompts_handler.get_cached_prompt = AsyncMock(
                return_value="(fake hyde template here)"
            )

    return MockProviders()


@pytest.fixture
def retrieval_service(mock_providers):
    """
    Construct your RetrievalService with the mocked providers.
    """
    from core import R2RConfig  # adjust import as needed

    config = R2RConfig({})  # or however you normally build it
    providers = mock_providers
    # If your constructor is something like:
    from core.main.services import RetrievalService  # example

    service = RetrievalService(config=config, providers=providers)
    return service


# @pytest.mark.asyncio
# async def test_basic_search_calls_once(retrieval_service):
#     """
#     Ensure that in 'basic' strategy, we only do 1 chunk search & 1 graph search
#     (assuming use_semantic_search=True and chunk_settings.enabled=True, etc.).
#     """
#     s = SearchSettings(
#         search_strategy="vanilla",  # or "basic"
#         use_semantic_search=True,
#         chunk_settings={"enabled": True},
#         graph_settings={"enabled": True},
#     )
#     await retrieval_service.search("Aristotle", s)

#     # we expect 1 call to chunk search, 1 call to graph search
#     chunk_handler = retrieval_service.providers.database.chunks_handler
#     graph_handler = retrieval_service.providers.database.graphs_handler

#     # Because we used semantic_search or hybrid, let's see which was called:
#     # If your code used hybrid by default, check `hybrid_search.call_count`
#     assert (
#         chunk_handler.hybrid_search.call_count
#         + chunk_handler.semantic_search.call_count
#         + chunk_handler.full_text_search.call_count
#         == 1
#     ), "Expected exactly 1 chunk search call in basic mode"
#     assert (
#         graph_handler.graph_search.call_count == 3
#     ), "Expected exactly 1 graph search call in basic mode"




# @pytest.mark.asyncio
# async def test_hyde_search_fans_out_correctly(retrieval_service):
#     """
#     In 'hyde' strategy with num_sub_queries=2, we should:
#       - generate 2 hypothetical docs
#       - for each doc => embed alt_text => run chunk+graph => total 2 chunk searches, 2 graph searches
#     """
#     s = SearchSettings(
#         search_strategy="hyde",
#         num_sub_queries=2,
#         use_semantic_search=True,
#         chunk_settings={"enabled": True},
#         graph_settings={"enabled": True},
#     )
#     await retrieval_service.search("Aristotle", s)

#     chunk_handler = retrieval_service.providers.database.chunks_handler
#     graph_handler = retrieval_service.providers.database.graphs_handler
#     embedding_mock = (
#         retrieval_service.providers.completion_embedding.async_get_embedding
#     )
#     # For chunk search, each sub-query => 1 chunk search => total 2 calls
#     # (If you see more, maybe your code does something else.)
#     total_chunk_calls = (
#         chunk_handler.hybrid_search.call_count
#         + chunk_handler.semantic_search.call_count
#         + chunk_handler.full_text_search.call_count
#     )
#     print('total_chunk_calls = ', total_chunk_calls)

#     # Check how many times we called embedding
#     # 1) Possibly the code might embed "Aristotle" once if it re-ranks with user_text (though you might not do that).
#     # 2) The code definitely calls embed for each "hyde doc" -> 2 sub queries => 2 calls
#     # So you might see 2 or 3 total calls
#     assert (
#         embedding_mock.call_count >= 2
#     ), "We expected at least 2 embeddings for the hyde docs"

#     assert (
#         total_chunk_calls == 2
#     ), f"Expected exactly 2 chunk search calls (got {total_chunk_calls})"

#     # For graph search => also 2 calls
#     assert (
#         graph_handler.graph_search.call_count == 2
#     ), f"Expected exactly 2 graph search calls, got {graph_handler.graph_search.call_count}"


# @pytest.mark.asyncio
# async def test_rag_fusion_placeholder(retrieval_service):
#     """
#     We have a placeholder `_rag_fusion_search`, but it just calls `_basic_search`.
#     So let's verify it just triggers 1 chunk search / 1 graph search by default.
#     """
#     s = SearchSettings(
#         search_strategy="rag_fusion",
#         # if you haven't actually implemented multi-subqueries, it should
#         # just do the same as basic (1 chunk search, 1 graph search).
#         use_semantic_search=True,
#         chunk_settings={"enabled": True},
#         graph_settings={"enabled": True},
#     )
#     await retrieval_service.search("Aristotle", s)

#     chunk_handler = retrieval_service.providers.database.chunks_handler
#     graph_handler = retrieval_service.providers.database.graphs_handler

#     total_chunk_calls = (
#         chunk_handler.hybrid_search.call_count
#         + chunk_handler.semantic_search.call_count
#         + chunk_handler.full_text_search.call_count
#     )
#     assert (
#         total_chunk_calls == 1
#     ), "Placeholder RAG-Fusion should call 1 chunk search"
#     assert (
#         graph_handler.graph_search.call_count == 3
#     ), "Placeholder RAG-Fusion => 1 graph search"
