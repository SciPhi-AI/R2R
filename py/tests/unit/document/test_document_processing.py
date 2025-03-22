import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, List, Any, Optional

# Import necessary classes
from core.base import Document, Chunk


@pytest.fixture
def sample_document():
    """Return a sample document for testing."""
    return Document(
        document_id="doc-123",
        raw_text="Aristotle was a Greek philosopher who studied under Plato. He made significant contributions to logic, ethics, and metaphysics.",
        metadata={
            "source": "Philosophy Encyclopedia",
            "author": "Academic Press",
            "year": 2020,
            "document_type": "text"
        },
        chunks=[
            Chunk(
                chunk_id="chunk-1",
                document_id="doc-123",
                text="Aristotle was a Greek philosopher who studied under Plato.",
                metadata={"section": "biography", "page": 1}
            ),
            Chunk(
                chunk_id="chunk-2",
                document_id="doc-123",
                text="He made significant contributions to logic, ethics, and metaphysics.",
                metadata={"section": "contributions", "page": 1}
            )
        ]
    )


@pytest.fixture
def mock_document_handler():
    """Return a mock document handler."""
    handler = AsyncMock()
    handler.get_document_by_id = AsyncMock()
    handler.create_document = AsyncMock()
    handler.update_document = AsyncMock()
    handler.delete_document = AsyncMock()
    return handler


@pytest.mark.asyncio
async def test_document_chunking(mock_document_handler, sample_document):
    """Test document chunking functionality."""
    from core.main.services.documents import DocumentProcessingService
    
    # Setup the chunking service with mocked components
    service = DocumentProcessingService(document_handler=mock_document_handler)
    
    # Mock the chunking method
    original_chunk_method = service.chunk_document
    service.chunk_document = MagicMock(return_value=[
        Chunk(
            chunk_id="new-chunk-1",
            document_id=sample_document.document_id,
            text="Aristotle was a Greek philosopher.",
            metadata={"auto_chunk": True}
        ),
        Chunk(
            chunk_id="new-chunk-2",
            document_id=sample_document.document_id,
            text="He studied under Plato.",
            metadata={"auto_chunk": True}
        ),
        Chunk(
            chunk_id="new-chunk-3",
            document_id=sample_document.document_id,
            text="He made significant contributions to logic, ethics, and metaphysics.",
            metadata={"auto_chunk": True}
        )
    ])
    
    # Process the document
    processed_doc = await service.process_document(sample_document)
    
    # Verify chunking was called
    service.chunk_document.assert_called_once()
    
    # Check that document was updated with new chunks
    assert len(processed_doc.chunks) == 3
    assert all(chunk.metadata.get("auto_chunk") for chunk in processed_doc.chunks)
    
    # Restore original method
    service.chunk_document = original_chunk_method


@pytest.mark.asyncio
async def test_document_metadata_extraction(mock_document_handler, sample_document):
    """Test metadata extraction from documents."""
    from core.main.services.documents import DocumentProcessingService
    
    # Setup the document processing service
    service = DocumentProcessingService(document_handler=mock_document_handler)
    
    # Mock metadata extraction
    original_extract_method = service.extract_metadata
    service.extract_metadata = MagicMock(return_value={
        "title": "Aristotle: Life and Works",
        "topics": ["philosophy", "logic", "ethics"],
        "sentiment": "neutral",
        "word_count": 24
    })
    
    # Process the document
    processed_doc = await service.process_document(sample_document, extract_metadata=True)
    
    # Verify metadata extraction was called
    service.extract_metadata.assert_called_once_with(sample_document.raw_text)
    
    # Check that document metadata was updated
    for key, value in service.extract_metadata.return_value.items():
        assert processed_doc.metadata.get(key) == value
    
    # Restore original method
    service.extract_metadata = original_extract_method


@pytest.mark.asyncio
async def test_document_embedding_generation(mock_document_handler, sample_document):
    """Test embedding generation for document chunks."""
    from core.main.services.documents import DocumentProcessingService
    
    # Setup mock embedding provider
    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.async_get_embedding = AsyncMock(
        return_value=[0.1, 0.2, 0.3, 0.4]
    )
    
    # Setup document processing service
    service = DocumentProcessingService(
        document_handler=mock_document_handler,
        embedding_provider=mock_embedding_provider
    )
    
    # Process document with embedding generation
    processed_doc = await service.process_document(
        sample_document, 
        generate_embeddings=True
    )
    
    # Verify embedding provider was called for each chunk
    assert mock_embedding_provider.async_get_embedding.call_count == len(sample_document.chunks)
    
    # Check that embeddings were stored with chunks
    for chunk in processed_doc.chunks:
        assert hasattr(chunk, "embedding")
        assert chunk.embedding == [0.1, 0.2, 0.3, 0.4]


@pytest.mark.asyncio
async def test_document_citation_processing(mock_document_handler, sample_document):
    """Test citation extraction and processing in documents."""
    from core.main.services.documents import DocumentProcessingService
    
    # Add citation markers to document text
    document_with_citations = Document(
        document_id="doc-456",
        raw_text="According to Smith [abc123], Aristotle developed formal logic. Jones [def456] argues that his ethics were revolutionary.",
        metadata={"source": "Academic Journal"}
    )
    
    # Setup document processing service
    service = DocumentProcessingService(document_handler=mock_document_handler)
    
    # Mock citation extraction method
    original_extract_citations = service.extract_citations
    service.extract_citations = MagicMock(return_value=[
        {"id": "abc123", "span": "According to Smith [abc123]", "start": 0, "end": 25},
        {"id": "def456", "span": "Jones [def456]", "start": 54, "end": 68}
    ])
    
    # Process document with citation extraction
    processed_doc = await service.process_document(
        document_with_citations,
        extract_citations=True
    )
    
    # Verify citation extraction was called
    service.extract_citations.assert_called_once_with(document_with_citations.raw_text)
    
    # Check that citations were stored with the document
    assert "citations" in processed_doc.metadata
    assert len(processed_doc.metadata["citations"]) == 2
    assert processed_doc.metadata["citations"][0]["id"] == "abc123"
    assert processed_doc.metadata["citations"][1]["id"] == "def456"
    
    # Restore original method
    service.extract_citations = original_extract_citations


@pytest.mark.asyncio
async def test_document_text_preprocessing(mock_document_handler):
    """Test text preprocessing for documents."""
    from core.main.services.documents import DocumentProcessingService
    
    # Setup document with formatting issues
    document_with_formatting = Document(
        document_id="doc-789",
        raw_text="  Aristotle  was\n\na Greek\tphilosopher.   He studied\nunder Plato.  ",
        metadata={}
    )
    
    # Setup document processing service
    service = DocumentProcessingService(document_handler=mock_document_handler)
    
    # Mock text preprocessing method
    original_preprocess = service.preprocess_text
    service.preprocess_text = MagicMock(return_value="Aristotle was a Greek philosopher. He studied under Plato.")
    
    # Process document with preprocessing
    processed_doc = await service.process_document(
        document_with_formatting,
        preprocess_text=True
    )
    
    # Verify preprocessing was called
    service.preprocess_text.assert_called_once_with(document_with_formatting.raw_text)
    
    # Check that document text was preprocessed
    assert processed_doc.raw_text == "Aristotle was a Greek philosopher. He studied under Plato."
    
    # Restore original method
    service.preprocess_text = original_preprocess
