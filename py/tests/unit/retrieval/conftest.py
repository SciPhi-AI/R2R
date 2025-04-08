"""
Common test fixtures for retrieval tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Optional


class MockSearchSettings:
    """Mock class for SearchSettings to avoid dependency issues."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        # Set defaults for commonly used attributes
        for attr in ['use_semantic_search', 'use_hybrid_search', 'use_full_text_search',
                    'use_graph_search', 'filters', 'limit', 'offset', 'search_strategy',
                    'num_sub_queries', 'use_citation_search', 'hybrid_settings']:
            if not hasattr(self, attr):
                setattr(self, attr, None)

        # Default values
        if self.search_strategy is None:
            self.search_strategy = "basic"
        if self.limit is None:
            self.limit = 10
        if self.filters is None:
            self.filters = {}
        if self.offset is None:
            self.offset = 0
        if self.num_sub_queries is None:
            self.num_sub_queries = 3
        if self.hybrid_settings is None:
            self.hybrid_settings = {
                "semantic_weight": 0.5,
                "full_text_weight": 0.5
            }


class MockDocument:
    """Mock Document class for testing."""
    def __init__(self, document_id, raw_text, metadata=None, chunks=None):
        self.document_id = document_id
        self.raw_text = raw_text
        self.metadata = metadata or {}
        self.chunks = chunks or []


class MockChunk:
    """Mock Chunk class for testing."""
    def __init__(self, chunk_id, document_id, text, metadata=None):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.text = text
        self.metadata = metadata or {}
        self.embedding = None


class MockCitation:
    """Mock Citation class for testing."""
    def __init__(self, citation_id, text, metadata=None, source=None):
        self.citation_id = citation_id
        self.text = text
        self.metadata = metadata or {}
        self.source = source or "unknown"


@pytest.fixture
def mock_providers():
    """Return a mocked providers object for testing."""
    class MockProviders:
        def __init__(self):
            # Mock the embedding provider
            self.completion_embedding = AsyncMock()
            self.completion_embedding.async_get_embedding = AsyncMock(
                return_value=[0.123] * 768  # pretend vector
            )

            # Mock the database chunks handler
            self.database = AsyncMock()
            self.database.chunks_handler = AsyncMock()
            self.database.chunks_handler.semantic_search = AsyncMock(
                return_value=[
                    {
                        "chunk_id": f"chunk-{i}",
                        "document_id": f"doc-{i//2}",
                        "text": f"This is search result {i} about philosophy.",
                        "metadata": {"source": f"source-{i}"},
                        "score": 0.95 - (i * 0.05),
                    }
                    for i in range(5)
                ]
            )
            self.database.chunks_handler.full_text_search = AsyncMock(
                return_value=[
                    {
                        "chunk_id": f"chunk-ft-{i}",
                        "document_id": f"doc-ft-{i//2}",
                        "text": f"Full-text search result {i} about philosophy.",
                        "metadata": {"source": f"ft-source-{i}"},
                        "score": 0.9 - (i * 0.05),
                    }
                    for i in range(5)
                ]
            )
            self.database.chunks_handler.hybrid_search = AsyncMock(
                return_value=[
                    {
                        "chunk_id": f"chunk-hybrid-{i}",
                        "document_id": f"doc-hybrid-{i//2}",
                        "text": f"Hybrid search result {i} about philosophy.",
                        "metadata": {"source": f"hybrid-source-{i}"},
                        "score": 0.92 - (i * 0.05),
                    }
                    for i in range(5)
                ]
            )

            # Mock graphs handler
            self.database.graphs_handler = AsyncMock()
            self.database.graphs_handler.graph_search = AsyncMock(
                return_value=iter([
                    {
                        "node_id": f"node-{i}",
                        "document_id": f"doc-{i}",
                        "text": f"Graph search result {i}.",
                        "score": 0.85 - (i * 0.05),
                    }
                    for i in range(3)
                ])
            )

            # Mock citation handler
            self.database.citations_handler = AsyncMock()
            self.database.citations_handler.get_citations = AsyncMock(
                return_value=[
                    MockCitation(
                        citation_id=f"cite-{i}",
                        text=f"Citation {i} from an important source.",
                        metadata={"author": f"Author {i}", "year": 2020 + i},
                        source=f"Book {i}"
                    )
                    for i in range(3)
                ]
            )

            # Mock LLM
            self.llm = AsyncMock()
            self.llm.aget_completion = AsyncMock(
                return_value={"choices": [{"message": {"content": "LLM generated response about philosophy"}}]}
            )
            self.llm.aget_completion_stream = AsyncMock(
                return_value=iter([
                    {"choices": [{"delta": {"content": "Streamed "}}]},
                    {"choices": [{"delta": {"content": "response "}}]},
                    {"choices": [{"delta": {"content": "about "}}]},
                    {"choices": [{"delta": {"content": "philosophy"}}]}
                ])
            )

            # Mock prompts handler
            self.database.prompts_handler = AsyncMock()
            self.database.prompts_handler.get_cached_prompt = AsyncMock(
                return_value="System prompt with {{context}} and {{query}} placeholders"
            )

            # Set up different prompt templates
            self.prompts = {
                "default": "Answer based on the following context: {{context}}\n\nQuery: {{query}}",
                "hyde_template": "Generate a hypothetical document about: {{query}}",
                "rag_fusion": "Generate {num_queries} search queries related to: {{query}}",
                "citation_format": "Format citation for {{source}}: {{text}}"
            }

            # Update get_cached_prompt to use different templates
            async def get_cached_prompt(prompt_id):
                return self.prompts.get(prompt_id, self.prompts["default"])

            self.database.prompts_handler.get_cached_prompt.side_effect = get_cached_prompt

    return MockProviders()


@pytest.fixture
def sample_chunk_results():
    """Sample chunk results for testing."""
    return [
        {
            "chunk_id": f"chunk-{i}",
            "document_id": f"doc-{i//2}",
            "text": f"This is chunk {i} about philosophy.",
            "metadata": {"source": f"source-{i}", "page": i + 1},
            "score": 0.95 - (i * 0.05),
        }
        for i in range(5)
    ]


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        MockDocument(
            document_id=f"doc-{i}",
            raw_text=f"This is document {i} about philosophy with multiple paragraphs.\n\n"
                    f"It contains information from various sources and perspectives.",
            metadata={"title": f"Philosophy Text {i}", "author": f"Author {i}"}
        )
        for i in range(3)
    ]
