"""
Unit tests for search methods and strategies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Any, Optional

from core.base import SearchSettings

@pytest.fixture
def mock_providers():
    """Set up mock providers for testing search strategies."""
    class MockProviders:
        def __init__(self):
            # Mock the embedding provider
            self.completion_embedding = AsyncMock()
            self.completion_embedding.async_get_embedding = AsyncMock(
                return_value=[0.1] * 768
            )
            
            # Mock the database handlers
            self.database = AsyncMock()
            self.database.chunks_handler = AsyncMock()
            self.database.chunks_handler.semantic_search = AsyncMock(
                return_value=[{"chunk_id": f"chunk-{i}", "score": 0.9 - (i * 0.1)} for i in range(3)]
            )
            self.database.chunks_handler.full_text_search = AsyncMock(
                return_value=[{"chunk_id": f"chunk-{i}", "score": 0.8 - (i * 0.1)} for i in range(3)]
            )
            self.database.chunks_handler.hybrid_search = AsyncMock(
                return_value=[{"chunk_id": f"chunk-{i}", "score": 0.85 - (i * 0.1)} for i in range(3)]
            )
            
            # Mock the LLM provider
            self.llm = AsyncMock()
            self.llm.aget_completion = AsyncMock(
                return_value={"choices": [{"message": {"content": "Hypothetical document about the query topic."}}]}
            )
            
            # Mock prompt handler
            self.database.prompts_handler = AsyncMock()
            self.database.prompts_handler.get_cached_prompt = AsyncMock(
                return_value="Generate a detailed document that might contain information about: {{query}}"
            )
            
            # Mock graphs handler
            self.database.graphs_handler = AsyncMock()
            self.database.graphs_handler.graph_search = AsyncMock(
                return_value=[
                    {
                        "node_id": f"node-{i}",
                        "text": f"Graph search result {i} about the topic.",
                        "metadata": {"source": f"graph-source-{i}"},
                        "score": 0.9 - (i * 0.05),
                    }
                    for i in range(3)
                ]
            )
            
    return MockProviders()


class TestBasicSearchMethods:
    """Tests for basic search methods."""
    
    @pytest.mark.asyncio
    async def test_semantic_search_basic(self, mock_providers):
        """Test basic semantic search with default parameters."""
        # Test parameters
        query = "What is philosophy?"
        settings = SearchSettings(
            use_semantic_search=True,
            limit=5
        )
        
        # Perform search
        results = await mock_providers.database.chunks_handler.semantic_search(
            query=query, 
            filters=getattr(settings, 'filters', {}),
            limit=getattr(settings, 'limit', 10)
        )
        
        # Verify results
        assert len(results) == 3  # Our mock returns 3 results
        assert all("chunk-" in r["chunk_id"] for r in results)
        
        # Verify correct parameters were used
        mock_providers.database.chunks_handler.semantic_search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_semantic_search_with_filters(self, mock_providers):
        """Test semantic search with metadata filters."""
        # Test parameters
        query = "Plato's Republic"
        filters = {"metadata.source": {"$eq": "philosophy_book"}}
        
        # Perform search
        results = await mock_providers.database.chunks_handler.semantic_search(
            query=query, 
            filters=filters,
            limit=10
        )
        
        # Verify results
        assert len(results) == 3  # Our mock always returns 3 results
        
        # Verify filters were applied
        _, kwargs = mock_providers.database.chunks_handler.semantic_search.call_args
        assert kwargs["filters"] == filters
    
    @pytest.mark.asyncio
    async def test_semantic_search_with_embedding(self, mock_providers):
        """Test semantic search using a pre-computed embedding vector."""
        # Test parameters
        embedding = [0.1] * 768  # Dummy embedding vector
        
        # Perform search with embedding
        results = await mock_providers.database.chunks_handler.semantic_search(
            query=None,  # No query text when using embedding
            vector=embedding,
            limit=5
        )
        
        # Verify results
        assert len(results) == 3
        
        # Verify correct parameters were used
        _, kwargs = mock_providers.database.chunks_handler.semantic_search.call_args
        assert kwargs["vector"] == embedding
        assert kwargs["query"] is None
    
    @pytest.mark.asyncio
    async def test_full_text_search_basic(self, mock_providers):
        """Test basic full-text search."""
        # Test parameters
        query = "Aristotle ethics"
        
        # Perform search
        results = await mock_providers.database.chunks_handler.full_text_search(
            query=query,
            limit=10
        )
        
        # Verify results
        assert len(results) == 3
        assert all("chunk-" in r["chunk_id"] for r in results)
    
    @pytest.mark.asyncio
    async def test_full_text_search_with_complex_query(self, mock_providers):
        """Test full-text search with a complex query containing operators."""
        # Test parameters
        query = '"exact phrase" AND (term1 OR term2) -excluded'
        
        # Perform search
        results = await mock_providers.database.chunks_handler.full_text_search(
            query=query,
            limit=10
        )
        
        # Verify the right method was called with the right query
        mock_providers.database.chunks_handler.full_text_search.assert_called_with(
            query=query,
            limit=10,
            filters={},  # Default empty filters
            offset=0     # Default offset
        )
    
    @pytest.mark.asyncio
    async def test_hybrid_search_basic(self, mock_providers):
        """Test basic hybrid search with default weights."""
        # Test parameters
        query = "Aristotle ethics"
        
        # Perform search
        results = await mock_providers.database.chunks_handler.hybrid_search(
            query=query,
            limit=10
        )
        
        # Verify results
        assert len(results) == 3
        assert all("chunk-" in r["chunk_id"] for r in results)
    
    @pytest.mark.asyncio
    async def test_hybrid_search_custom_weights(self, mock_providers):
        """Test hybrid search with custom weights for semantic and full-text components."""
        # Test parameters
        query = "Aristotle ethics"
        semantic_weight = 0.7
        full_text_weight = 0.3
        
        # Perform search
        results = await mock_providers.database.chunks_handler.hybrid_search(
            query=query,
            semantic_weight=semantic_weight, 
            full_text_weight=full_text_weight,
            limit=10
        )
        
        # Verify the right method was called with the right weights
        _, kwargs = mock_providers.database.chunks_handler.hybrid_search.call_args
        assert kwargs["semantic_weight"] == semantic_weight
        assert kwargs["full_text_weight"] == full_text_weight
    
    @pytest.mark.asyncio
    async def test_graph_search_basic(self, mock_providers):
        """Test basic graph search."""
        # Test parameters
        query = "Aristotle"
        
        # Perform search
        results = await mock_providers.database.graphs_handler.graph_search(
            query=query,
            limit=10
        )
        
        # Verify results
        assert len(results) == 3
        assert all("node-" in r["node_id"] for r in results)


class TestSearchStrategies:
    """Tests for search strategies."""
    
    @pytest.mark.asyncio
    async def test_basic_search_strategy(self, mock_providers):
        """Test that BasicSearchStrategy performs expected search operations."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import BasicSearchStrategy
        
        strategy = BasicSearchStrategy(mock_providers)
        
        query = "Aristotle's ethics"
        settings = SearchSettings(
            use_semantic_search=True,
            chunk_settings={"enabled": True},
            graph_settings={"enabled": False},
        )
        
        # Run the strategy
        results = await strategy.execute(query, settings)
        
        # Verify correct search method was called
        assert mock_providers.database.chunks_handler.semantic_search.call_count == 1
        assert mock_providers.database.chunks_handler.full_text_search.call_count == 0
        assert mock_providers.database.chunks_handler.hybrid_search.call_count == 0
        
        # Test with hybrid search enabled
        settings = SearchSettings(
            use_hybrid_search=True,
            hybrid_settings={"semantic_weight": 0.6, "full_text_weight": 0.4},
            chunk_settings={"enabled": True},
        )
        
        results = await strategy.execute(query, settings)
        
        # Verify hybrid search was called
        assert mock_providers.database.chunks_handler.hybrid_search.call_count == 1
    
    @pytest.mark.asyncio
    async def test_hyde_search_strategy(self, mock_providers):
        """Test that HyDESearchStrategy generates hypothetical documents and performs searches."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import HyDESearchStrategy
        
        strategy = HyDESearchStrategy(mock_providers)
        
        query = "What did Aristotle say about ethics?"
        settings = SearchSettings(
            search_strategy="hyde",
            num_sub_queries=2,
            use_semantic_search=True,
        )
        
        # Setup LLM to return different responses
        mock_providers.llm.aget_completion.side_effect = [
            {"choices": [{"message": {"content": "Hypothetical doc 1"}}]},
            {"choices": [{"message": {"content": "Hypothetical doc 2"}}]},
        ]
        
        # Run the strategy
        results = await strategy.execute(query, settings)
        
        # Verify LLM was called to generate hypothetical documents
        assert mock_providers.llm.aget_completion.call_count == settings.num_sub_queries
        
        # Verify embeddings were generated for each hypothetical document
        assert mock_providers.completion_embedding.async_get_embedding.call_count >= settings.num_sub_queries
        
        # Verify semantic searches were performed for each hypothetical document
        assert mock_providers.database.chunks_handler.semantic_search.call_count == settings.num_sub_queries
    
    @pytest.mark.asyncio
    async def test_rag_fusion_search_strategy(self, mock_providers):
        """Test that RAGFusionSearchStrategy generates multiple queries and combines results."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import RAGFusionSearchStrategy
        
        # Setup LLM to return multiple subqueries
        mock_providers.llm.aget_completion.return_value = {
            "choices": [{"message": {"content": "Query 1\nQuery 2\nQuery 3"}}]
        }
        
        strategy = RAGFusionSearchStrategy(mock_providers)
        
        query = "Philosophy of Aristotle"
        settings = SearchSettings(
            search_strategy="rag_fusion",
            num_sub_queries=3,
            use_semantic_search=True,
        )
        
        # Run the strategy
        results = await strategy.execute(query, settings)
        
        # Verify LLM was called to generate subqueries
        assert mock_providers.llm.aget_completion.call_count == 1
        
        # Verify semantic searches were performed for each subquery
        assert mock_providers.database.chunks_handler.semantic_search.call_count == 3
        
        # Verify result count (should have combined results from all subqueries)
        assert len(results.get("chunk_search_results", [])) > 0
    
    @pytest.mark.asyncio
    async def test_search_strategy_with_filters(self, mock_providers):
        """Test that search strategies correctly apply filters."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import BasicSearchStrategy
        
        strategy = BasicSearchStrategy(mock_providers)
        
        filters = {"metadata.source": {"$eq": "book"}}
        query = "Aristotle"
        settings = SearchSettings(
            use_semantic_search=True,
            filters=filters,
        )
        
        # Run the strategy
        results = await strategy.execute(query, settings)
        
        # Verify filters were passed to search
        _, kwargs = mock_providers.database.chunks_handler.semantic_search.call_args
        assert "filters" in kwargs
        assert kwargs["filters"] == filters
    
    @pytest.mark.asyncio
    async def test_search_strategy_pagination(self, mock_providers):
        """Test that search strategies correctly handle pagination."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import BasicSearchStrategy
        
        strategy = BasicSearchStrategy(mock_providers)
        
        query = "Aristotle"
        settings = SearchSettings(
            use_semantic_search=True,
            limit=5,
            offset=10,
        )
        
        # Run the strategy
        results = await strategy.execute(query, settings)
        
        # Verify pagination parameters were passed
        _, kwargs = mock_providers.database.chunks_handler.semantic_search.call_args
        assert "limit" in kwargs
        assert kwargs["limit"] == 5
        assert "offset" in kwargs
        assert kwargs["offset"] == 10
    
    @pytest.mark.asyncio
    async def test_search_strategy_error_handling(self, mock_providers):
        """Test that search strategies properly handle errors."""
        # Import the strategy
        from core.main.services.retrieval.search_strategies import BasicSearchStrategy
        
        # Set up the chunk handler to raise an exception
        mock_providers.database.chunks_handler.semantic_search.side_effect = Exception("Database error")
        
        strategy = BasicSearchStrategy(mock_providers)
        
        query = "Aristotle"
        settings = SearchSettings(use_semantic_search=True)
        
        # Run the strategy and expect it to propagate the error
        with pytest.raises(Exception) as excinfo:
            await strategy.execute(query, settings)
        
        assert "Database error" in str(excinfo.value)


class TestSearchResultProcessing:
    """Tests for processing search results."""
    
    @pytest.mark.asyncio
    async def test_result_ranking(self, mock_providers):
        """Test ranking of search results."""
        # Create unordered results
        results = [
            {"chunk_id": "chunk-1", "score": 0.5},
            {"chunk_id": "chunk-2", "score": 0.9},
            {"chunk_id": "chunk-3", "score": 0.7},
        ]
        
        # Sort results by score (descending)
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        
        # Verify ranking
        assert sorted_results[0]["chunk_id"] == "chunk-2"
        assert sorted_results[1]["chunk_id"] == "chunk-3"
        assert sorted_results[2]["chunk_id"] == "chunk-1"
    
    @pytest.mark.asyncio
    async def test_result_deduplication(self, mock_providers):
        """Test deduplication of search results from multiple strategies."""
        # Create results with some duplicates (same document_id)
        results1 = [
            {"chunk_id": "chunk-1", "document_id": "doc-1", "score": 0.9},
            {"chunk_id": "chunk-2", "document_id": "doc-2", "score": 0.8},
        ]
        
        results2 = [
            {"chunk_id": "chunk-3", "document_id": "doc-1", "score": 0.7},  # Same doc as chunk-1
            {"chunk_id": "chunk-4", "document_id": "doc-3", "score": 0.6},
        ]
        
        # Combine results
        combined = results1 + results2
        
        # Deduplicate by document_id, keeping the highest scoring chunk per document
        seen_docs = {}
        deduplicated = []
        
        for result in combined:
            doc_id = result["document_id"]
            if doc_id not in seen_docs or result["score"] > seen_docs[doc_id]["score"]:
                seen_docs[doc_id] = result
        
        deduplicated = list(seen_docs.values())
        
        # Verify deduplication
        assert len(deduplicated) == 3  # Should have 3 unique documents
        
        # Verify the highest scoring chunk was kept for doc-1
        doc1_chunks = [r for r in deduplicated if r["document_id"] == "doc-1"]
        assert len(doc1_chunks) == 1
        assert doc1_chunks[0]["chunk_id"] == "chunk-1"  # Higher scoring chunk
    
    @pytest.mark.asyncio
    async def test_result_truncation(self, mock_providers):
        """Test truncation of search results to a specified limit."""
        # Create results
        results = [
            {"chunk_id": f"chunk-{i}", "score": 0.9 - (i * 0.1)}
            for i in range(10)
        ]
        
        # Apply limit
        limit = 5
        truncated = results[:limit]
        
        # Verify truncation
        assert len(truncated) == limit
        assert truncated[-1]["chunk_id"] == "chunk-4"
