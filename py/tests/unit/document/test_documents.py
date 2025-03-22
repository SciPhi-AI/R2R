import json
import uuid

import pytest

from core.base import (
    DocumentResponse,
    DocumentType,
    GraphExtractionStatus,
    IngestionStatus,
)


def make_db_entry(doc: DocumentResponse):
    # This simulates what your real code should do:
    return {
        "id":
        doc.id,
        "collection_ids":
        doc.collection_ids,
        "owner_id":
        doc.owner_id,
        "document_type":
        doc.document_type.value,
        "metadata":
        json.dumps(doc.metadata),
        "title":
        doc.title,
        "version":
        doc.version,
        "size_in_bytes":
        doc.size_in_bytes,
        "ingestion_status":
        doc.ingestion_status.value,
        "extraction_status":
        doc.extraction_status.value,
        "created_at":
        doc.created_at,
        "updated_at":
        doc.updated_at,
        "ingestion_attempt_number":
        0,
        "summary":
        doc.summary,
        # If summary_embedding is a list, we can store it as a string here if needed
        "summary_embedding": (str(doc.summary_embedding)
                              if doc.summary_embedding is not None else None),
    }


@pytest.mark.asyncio
async def test_upsert_documents_overview_insert(documents_handler):
    doc_id = uuid.uuid4()
    doc = DocumentResponse(
        id=doc_id,
        collection_ids=[],
        owner_id=uuid.uuid4(),
        document_type=DocumentType.TXT,
        metadata={"description": "A test document"},
        title="Test Doc",
        version="v1",
        size_in_bytes=1234,
        ingestion_status=IngestionStatus.PENDING,
        extraction_status=GraphExtractionStatus.PENDING,
        created_at=None,
        updated_at=None,
        summary=None,
        summary_embedding=None,
    )

    # Simulate the handler call
    await documents_handler.upsert_documents_overview(
        [doc])  # adjust your handler to accept list or doc
    # If your handler expects a db entry dict, you may need to patch handler or adapt your code

    # Verify
    res = await documents_handler.get_documents_overview(
        offset=0, limit=10, filter_document_ids=[doc_id])
    assert res["total_entries"] == 1
    fetched_doc = res["results"][0]
    assert fetched_doc.id == doc_id
    assert fetched_doc.title == "Test Doc"
    assert fetched_doc.metadata["description"] == "A test document"


@pytest.mark.asyncio
async def test_upsert_documents_overview_update(documents_handler):
    doc_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    doc = DocumentResponse(
        id=doc_id,
        collection_ids=[],
        owner_id=owner_id,
        document_type=DocumentType.TXT,
        metadata={"note": "initial"},
        title="Initial Title",
        version="v1",
        size_in_bytes=100,
        ingestion_status=IngestionStatus.PENDING,
        extraction_status=GraphExtractionStatus.PENDING,
        created_at=None,
        updated_at=None,
        summary=None,
        summary_embedding=None,
    )

    await documents_handler.upsert_documents_overview([doc])

    # Update document
    doc.title = "Updated Title"
    doc.metadata["note"] = "updated"

    await documents_handler.upsert_documents_overview([doc])

    # Verify update
    res = await documents_handler.get_documents_overview(
        offset=0, limit=10, filter_document_ids=[doc_id])
    fetched_doc = res["results"][0]
    assert fetched_doc.title == "Updated Title"
    assert fetched_doc.metadata["note"] == "updated"


@pytest.mark.asyncio
async def test_delete_document(documents_handler):
    doc_id = uuid.uuid4()
    doc = DocumentResponse(
        id=doc_id,
        collection_ids=[],
        owner_id=uuid.uuid4(),
        document_type=DocumentType.TXT,
        metadata={},
        title="ToDelete",
        version="v1",
        size_in_bytes=100,
        ingestion_status=IngestionStatus.PENDING,
        extraction_status=GraphExtractionStatus.PENDING,
        created_at=None,
        updated_at=None,
        summary=None,
        summary_embedding=None,
    )

    await documents_handler.upsert_documents_overview([doc])
    await documents_handler.delete(doc_id)
    res = await documents_handler.get_documents_overview(
        offset=0, limit=10, filter_document_ids=[doc_id])
    assert res["total_entries"] == 0
