"""
Unit tests for core retrieval functionality.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Any, Optional

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
            self.database.chunks_handler = AsyncMock()
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
            self.database.graphs_handler = AsyncMock()
            self.database.graphs_handler.graph_search = AsyncMock(
                return_value=iter([])
            )

            # Mock the LLM provider
            self.llm = AsyncMock()
            self.llm.aget_completion = AsyncMock(return_value={"choices": [{"message": {"content": "mocked content"}}]})
            self.llm.aget_completion_stream = AsyncMock(return_value=iter([{"choices": [{"delta": {"content": "chunk"}}]}]))

            # Mock prompt handler
            self.database.prompts_handler = AsyncMock()
            self.database.prompts_handler.get_cached_prompt = AsyncMock(
                return_value="(fake hyde template here)"
            )
            
            # Mock document handler
            self.database.documents_handler = AsyncMock()
            self.database.documents_handler.get_document_by_id = AsyncMock(
                return_value={"document_id": "mock-doc-123", "raw_text": "Mock document content"}
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


@pytest.fixture
def mock_chunk_results():
    """Return mock search results for testing."""
    return [
        {
            "chunk_id": f"chunk-{i}",
            "document_id": f"doc-{i//2}",
            "text": f"Mock chunk content {i}",
            "metadata": {"source": f"source-{i}"},
            "score": 0.95 - (i * 0.05),
        }
        for i in range(5)
    ]


class TestRetrievalBasics:
    """
    Tests for basic retrieval functionality.
    """
    
    @pytest.mark.asyncio
    async def test_basic_search_calls_once(self, retrieval_service):
        """
        Ensure that in 'basic' strategy, we only do 1 chunk search & 1 graph search.
        """
        s = SearchSettings(
            search_strategy="vanilla",  # or "basic"
            use_semantic_search=True,
            chunk_settings={"enabled": True},
            graph_settings={"enabled": True},
        )
        await retrieval_service.search("Aristotle", s)

        # we expect 1 call to chunk search, 1 call to graph search
        chunk_handler = retrieval_service.providers.database.chunks_handler
        graph_handler = retrieval_service.providers.database.graphs_handler

        # Because we used semantic_search or hybrid, let's see which was called:
        assert (
            chunk_handler.hybrid_search.call_count
            + chunk_handler.semantic_search.call_count
            + chunk_handler.full_text_search.call_count
            == 1
        ), "Expected exactly 1 chunk search call in basic mode"
        assert (
            graph_handler.graph_search.call_count == 1
        ), "Expected exactly 1 graph search call in basic mode"

    @pytest.mark.asyncio
    async def test_search_with_filters(self, retrieval_service):
        """Test that filters are correctly passed to search methods."""
        # Setup search settings with filters
        filters = {"metadata.source": "test-source"}
        s = SearchSettings(
            use_semantic_search=True,
            filters=filters,
        )
        
        # Perform search
        await retrieval_service.search("Aristotle", s)
        
        # Check filters were passed to the search method
        chunk_handler = retrieval_service.providers.database.chunks_handler
        _, kwargs = chunk_handler.semantic_search.call_args
        assert "filters" in kwargs
        assert kwargs["filters"] == filters
    
    @pytest.mark.asyncio 
    async def test_search_with_error_handling(self, retrieval_service):
        """Test error handling in search functionality."""
        # Make search method raise an exception
        retrieval_service.providers.database.chunks_handler.semantic_search.side_effect = Exception("Search failed")
        
        # Setup search settings
        s = SearchSettings(use_semantic_search=True)
        
        # The method should handle exceptions appropriately
        try:
            result = await retrieval_service.search("Aristotle", s)
            # Depending on your implementation, check if error is handled or populated in result
            # For example, check if result has an 'error' field:
            assert "error" in result
        except Exception as e:
            # Or if your implementation lets exceptions propagate, make sure they're the right ones
            assert "Search failed" in str(e)


class TestAdvancedSearchStrategies:
    """
    Tests for advanced search strategies like HyDE and RAG-fusion.
    """

    @pytest.mark.asyncio
    async def test_hyde_search_fans_out_correctly(self, retrieval_service):
        """
        In 'hyde' strategy with num_sub_queries=2, we should:
          - generate 2 hypothetical docs
          - for each doc => embed alt_text => run chunk+graph => total 2 chunk searches, 2 graph searches
        """
        # Setup LLM mock to return different responses for different calls
        retrieval_service.providers.llm.aget_completion.side_effect = [
            {"choices": [{"message": {"content": "Hypothetical doc 1"}}]},
            {"choices": [{"message": {"content": "Hypothetical doc 2"}}]},
        ]
        
        s = SearchSettings(
            search_strategy="hyde",
            num_sub_queries=2,
            use_semantic_search=True,
            chunk_settings={"enabled": True},
            graph_settings={"enabled": True},
        )
        await retrieval_service.search("Aristotle", s)

        chunk_handler = retrieval_service.providers.database.chunks_handler
        graph_handler = retrieval_service.providers.database.graphs_handler
        embedding_mock = (
            retrieval_service.providers.completion_embedding.async_get_embedding
        )
        # For chunk search, each sub-query => 1 chunk search => total 2 calls
        # (If you see more, maybe your code does something else.)
        total_chunk_calls = (
            chunk_handler.hybrid_search.call_count
            + chunk_handler.semantic_search.call_count
            + chunk_handler.full_text_search.call_count
        )

        # Check how many times we called embedding
        # 1) Possibly the code might embed "Aristotle" once if it re-ranks with user_text (though you might not do that).
        # 2) The code definitely calls embed for each "hyde doc" -> 2 sub queries => 2 calls
        # So you might see 2 or 3 total calls
        assert (
            embedding_mock.call_count >= 2
        ), "We expected at least 2 embeddings for the hyde docs"

        assert (
            total_chunk_calls == 2
        ), f"Expected exactly 2 chunk search calls (got {total_chunk_calls})"

        # For graph search => also 2 calls
        assert (
            graph_handler.graph_search.call_count == 2
        ), f"Expected exactly 2 graph search calls, got {graph_handler.graph_search.call_count}"
    
    @pytest.mark.asyncio
    async def test_rag_fusion_search(self, retrieval_service):
        """
        Test RAG-fusion search that generates multiple queries and reranks results.
        """
        # Mock LLM to return different subqueries
        retrieval_service.providers.llm.aget_completion.return_value = {
            "choices": [{
                "message": {
                    "content": "Query 1\nQuery 2\nQuery 3"
                }
            }]
        }
        
        # Mock the chunk handler to return different results for each search
        mock_results = [[{"chunk_id": f"chunk-{i}-{j}", "score": 0.9 - (0.1 * j)} for i in range(3)] for j in range(3)]
        retrieval_service.providers.database.chunks_handler.semantic_search.side_effect = mock_results
        
        s = SearchSettings(
            search_strategy="rag_fusion",
            num_sub_queries=3,
            use_semantic_search=True,
        )
        
        results = await retrieval_service.search("Philosophy", s)
        
        # Verify LLM was called to generate subqueries
        assert retrieval_service.providers.llm.aget_completion.call_count == 1
        
        # Verify multiple searches were performed
        assert retrieval_service.providers.database.chunks_handler.semantic_search.call_count == 3
        
        # Check that results were combined/reranked
        assert len(results.get("chunk_search_results", [])) > 0


class TestHybridSearchAndWeightBalancing:
    """
    Tests for hybrid search and weight balancing.
    """
    
    @pytest.mark.asyncio
    async def test_hybrid_search_weight_balancing(self, retrieval_service):
        """Test that hybrid search correctly balances semantic and full-text weights."""
        # Setup search settings with hybrid search enabled
        s = SearchSettings(
            use_hybrid_search=True,
            hybrid_settings={
                "semantic_weight": 0.7,
                "full_text_weight": 0.3
            }
        )
        
        # Perform search
        await retrieval_service.search("Aristotle", s)
        
        # Check hybrid search was called with correct weights
        chunk_handler = retrieval_service.providers.database.chunks_handler
        _, kwargs = chunk_handler.hybrid_search.call_args
        
        assert "semantic_weight" in kwargs
        assert "full_text_weight" in kwargs
        assert kwargs["semantic_weight"] == 0.7
        assert kwargs["full_text_weight"] == 0.3


class TestRAGPromptHandling:
    """
    Tests for RAG prompt handling and generation.
    """
    
    @pytest.mark.asyncio
    async def test_rag_query_processing(self, retrieval_service, mock_chunk_results):
        """Test RAG query processing and prompt construction."""
        # Mock the search results
        retrieval_service.search = AsyncMock(return_value={"chunk_search_results": mock_chunk_results})
        
        # When you call your RAG method (adapt this to your actual method name and signature)
        query = "What did Aristotle say about ethics?"
        
        # Assuming a method that prepares a RAG prompt
        # This is a simplification - adjust to your actual implementation
        async def prepare_rag_prompt(query):
            search_results = await retrieval_service.search(query, SearchSettings())
            chunks = search_results.get("chunk_search_results", [])
            
            # Assume you have a method that builds a context from chunks
            context = "\n".join([c["text"] for c in chunks])
            
            prompt_template = await retrieval_service.providers.database.prompts_handler.get_cached_prompt()
            prompt = prompt_template.replace("{{context}}", context).replace("{{query}}", query)
            
            return prompt
        
        prompt = await prepare_rag_prompt(query)
        
        # Verify search was called
        retrieval_service.search.assert_called_once()
        
        # Verify prompt contains expected elements
        assert "context" in prompt.lower()
        assert query in prompt
        assert any(chunk["text"] in prompt for chunk in mock_chunk_results)
    
    @pytest.mark.asyncio
    async def test_rag_streaming(self, retrieval_service, mock_chunk_results):
        """Test RAG streaming functionality."""
        # Mock search to return results
        retrieval_service.search = AsyncMock(return_value={"chunk_search_results": mock_chunk_results})
        
        # Mock LLM streaming
        stream_chunks = [
            {"choices": [{"delta": {"content": "This "}}]},
            {"choices": [{"delta": {"content": "is "}}]},
            {"choices": [{"delta": {"content": "a "}}]},
            {"choices": [{"delta": {"content": "streamed "}}]},
            {"choices": [{"delta": {"content": "response."}}]}
        ]
        retrieval_service.providers.llm.aget_completion_stream.return_value = iter(stream_chunks)
        
        # Create a collector for streamed chunks
        collected_chunks = []
        
        # Assuming a streaming method like this:
        async def stream_rag_response(query):
            # Prepare search results and prompt
            search_results = await retrieval_service.search(query, SearchSettings())
            chunks = search_results.get("chunk_search_results", [])
            context = "\n".join([c["text"] for c in chunks])
            
            prompt_template = await retrieval_service.providers.database.prompts_handler.get_cached_prompt()
            prompt = prompt_template.replace("{{context}}", context).replace("{{query}}", query)
            
            # Stream response
            async for chunk in retrieval_service.providers.llm.aget_completion_stream(prompt=prompt):
                yield chunk
        
        # Collect the streamed chunks
        async for chunk in stream_rag_response("What is philosophy?"):
            collected_chunks.append(chunk)
        
        # Verify search was called
        retrieval_service.search.assert_called_once()
        
        # Verify we got all the stream chunks
        assert len(collected_chunks) == len(stream_chunks)
        assert collected_chunks == stream_chunks
    
    @pytest.mark.asyncio
    async def test_rag_task_prompt_handling(self, retrieval_service, mock_chunk_results):
        """Test that task prompts are correctly incorporated into RAG prompts."""
        # Mock search to return results
        retrieval_service.search = AsyncMock(return_value={"chunk_search_results": mock_chunk_results})
        
        # Mock a task-specific prompt
        task_prompt = "Explain the following concepts in simple terms:"
        
        # When you call your RAG method with a task prompt
        query = "What is virtue ethics?"
        
        # Assuming a method that prepares a RAG prompt with task instructions
        async def prepare_rag_prompt_with_task(query, task_prompt):
            search_results = await retrieval_service.search(query, SearchSettings())
            chunks = search_results.get("chunk_search_results", [])
            context = "\n".join([c["text"] for c in chunks])
            
            prompt_template = await retrieval_service.providers.database.prompts_handler.get_cached_prompt()
            prompt = prompt_template.replace("{{context}}", context).replace("{{query}}", query)
            
            # Add task instructions
            prompt_with_task = f"{task_prompt}\n\n{prompt}"
            
            return prompt_with_task
        
        prompt = await prepare_rag_prompt_with_task(query, task_prompt)
        
        # Verify search was called
        retrieval_service.search.assert_called_once()
        
        # Verify prompt contains the task instructions
        assert task_prompt in prompt
        assert query in prompt
        assert any(chunk["text"] in prompt for chunk in mock_chunk_results)
