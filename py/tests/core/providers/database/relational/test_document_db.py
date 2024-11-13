# tests/providers/database/relational/test_document_db.py
from uuid import UUID

import pytest

from core.base import (
    DocumentResponse,
    DocumentType,
    IngestionStatus,
    KGEnrichmentStatus,
    KGExtractionStatus,
)

# @pytest.mark.asyncio
# async def test_create_table(temporary_postgres_db_provider):
#     await temporary_postgres_db_provider.create_tables()
#     # Verify that the table is created with the expected columns and constraints
#     # You can execute a query to check the table structure or use a database inspection tool


@pytest.mark.asyncio
async def test_upsert_documents_overview(temporary_postgres_db_provider):
    document_info = DocumentResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        collection_ids=[UUID("00000000-0000-0000-0000-000000000002")],
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        document_type=DocumentType.PDF,
        metadata={},
        title="Test Document",
        version="1.0",
        size_in_bytes=1024,
        ingestion_status=IngestionStatus.PENDING,
        kg_extraction_status=KGExtractionStatus.PENDING,
    )
    await temporary_postgres_db_provider.upsert_documents_overview(
        document_info
    )

    # Verify that the document is inserted correctly
    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_document_ids=[document_info.id]
    )
    assert len(result["results"]) == 1
    inserted_document = result["results"][0]
    assert inserted_document.id == document_info.id
    assert inserted_document.collection_ids == document_info.collection_ids
    assert inserted_document.user_id == document_info.user_id
    assert inserted_document.document_type == document_info.document_type
    assert inserted_document.metadata == document_info.metadata
    assert inserted_document.title == document_info.title
    assert inserted_document.version == document_info.version
    assert inserted_document.size_in_bytes == document_info.size_in_bytes
    assert inserted_document.ingestion_status == document_info.ingestion_status
    assert (
        inserted_document.kg_extraction_status
        == document_info.kg_extraction_status
    )

    # Update the document and verify the changes
    document_info.title = "Updated Test Document"
    document_info.ingestion_status = IngestionStatus.SUCCESS
    await temporary_postgres_db_provider.upsert_documents_overview(
        document_info
    )

    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_document_ids=[document_info.id]
    )
    assert len(result["results"]) == 1
    updated_document = result["results"][0]
    assert updated_document.title == "Updated Test Document"
    assert updated_document.ingestion_status == IngestionStatus.SUCCESS


@pytest.mark.asyncio
async def test_delete_from_documents_overview(temporary_postgres_db_provider):
    document_info = DocumentResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        collection_ids=[UUID("00000000-0000-0000-0000-000000000002")],
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        document_type=DocumentType.PDF,
        metadata={},
        title="Test Document",
        version="1.0",
        size_in_bytes=1024,
        ingestion_status=IngestionStatus.PENDING,
        kg_extraction_status=KGExtractionStatus.PENDING,
    )
    await temporary_postgres_db_provider.upsert_documents_overview(
        document_info
    )

    await temporary_postgres_db_provider.delete_from_documents_overview(
        document_info.id
    )

    # Verify that the document is deleted
    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_document_ids=[document_info.id]
    )
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_get_documents_overview(temporary_postgres_db_provider):
    document_info1 = DocumentResponse(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        collection_ids=[UUID("00000000-0000-0000-0000-000000000002")],
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        document_type=DocumentType.PDF,
        metadata={},
        title="Test Document 1",
        version="1.0",
        size_in_bytes=1024,
        ingestion_status=IngestionStatus.PENDING,
        kg_extraction_status=KGExtractionStatus.PENDING,
    )
    document_info2 = DocumentResponse(
        id=UUID("00000000-0000-0000-0000-000000000004"),
        collection_ids=[UUID("00000000-0000-0000-0000-000000000002")],
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        document_type=DocumentType.DOCX,
        metadata={},
        title="Test Document 2",
        version="1.0",
        size_in_bytes=2048,
        ingestion_status=IngestionStatus.SUCCESS,
        kg_extraction_status=KGExtractionStatus.PENDING,
    )
    await temporary_postgres_db_provider.upsert_documents_overview(
        [document_info1, document_info2]
    )

    # Test filtering by user ID
    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_user_ids=[UUID("00000000-0000-0000-0000-000000000003")]
    )
    assert len(result["results"]) == 2
    assert result["total_entries"] == 2

    # Test filtering by document ID
    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_document_ids=[UUID("00000000-0000-0000-0000-000000000001")]
    )
    assert len(result["results"]) == 1
    assert result["results"][0].id == UUID(
        "00000000-0000-0000-0000-000000000001"
    )

    # Test filtering by collection ID
    result = await temporary_postgres_db_provider.get_documents_overview(
        filter_collection_ids=[UUID("00000000-0000-0000-0000-000000000002")]
    )
    assert len(result["results"]) == 2
    assert result["total_entries"] == 2

    # Test pagination
    result = await temporary_postgres_db_provider.get_documents_overview(
        offset=1, limit=1
    )
    assert len(result["results"]) == 1
    assert result["total_entries"] == 2
