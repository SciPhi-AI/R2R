import time
import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture
def cleanup_documents(client: R2RClient):
    doc_ids = []

    def _track_document(doc_id):
        doc_ids.append(doc_id)
        return doc_id

    yield _track_document

    # Cleanup all documents
    for doc_id in doc_ids:
        try:
            client.documents.delete(id=doc_id)
        except R2RException:
            pass


def test_create_document_with_file(client: R2RClient, cleanup_documents):
    results = client.documents.create(
        file_path="core/examples/data/aristotle.txt",
        run_with_orchestration=False,
    ).results

    doc_id = cleanup_documents(results.document_id)
    assert results.document_id, "No document_id returned after file ingestion"


def test_create_document_with_raw_text(client: R2RClient, cleanup_documents):
    resp = client.documents.create(raw_text="This is raw text content.",
                                   run_with_orchestration=False)
    results = resp.results

    doc_id = cleanup_documents(results.document_id)
    assert doc_id, "No document_id returned after raw text ingestion"

    # Verify retrieval
    retrieved = client.documents.retrieve(id=doc_id)
    retrieved_results = retrieved.results
    assert retrieved_results.id == doc_id, (
        "Failed to retrieve the ingested raw text document")


def test_create_document_with_chunks(client: R2RClient, cleanup_documents):
    suffix = str(uuid.uuid4())[:8]
    resp = client.documents.create(
        chunks=[f"Chunk one{suffix}", f"Chunk two{suffix}"],
        run_with_orchestration=False,
    )
    results = resp.results

    doc_id = cleanup_documents(results.document_id)
    assert doc_id, "No document_id returned after chunk ingestion"

    retrieved = client.documents.retrieve(id=doc_id)
    retrieved_results = retrieved.results
    assert retrieved_results.id == doc_id, (
        "Failed to retrieve the chunk-based document")


def test_create_document_different_modes(client: R2RClient, cleanup_documents):
    # hi-res mode
    hi_res_resp = client.documents.create(
        raw_text="High resolution doc.",
        ingestion_mode="hi-res",
        run_with_orchestration=False,
    ).results
    hi_res_id = cleanup_documents(hi_res_resp.document_id)
    assert hi_res_id, "No doc_id returned for hi-res ingestion"

    # fast mode
    fast_resp = client.documents.create(
        raw_text="Fast mode doc.",
        ingestion_mode="fast",
        run_with_orchestration=False,
    ).results
    fast_id = cleanup_documents(fast_resp.document_id)
    assert fast_id, "No doc_id returned for fast ingestion"


def test_list_documents(client: R2RClient, test_document):
    results = client.documents.list(offset=0, limit=10).results
    assert isinstance(results, list), "Documents list response is not a list"
    assert len(results) >= 1, "Expected at least one document"
    # test_document is created for this test, so we expect at least that one present.


def test_retrieve_document(client: R2RClient, test_document):
    retrieved = client.documents.retrieve(id=test_document).results
    assert retrieved.id == test_document, "Retrieved wrong document"


def test_download_document(client: R2RClient, test_document):
    # For text-only documents, the endpoint returns text as a buffer
    content = client.documents.download(id=test_document)
    assert content, "Failed to download document content"
    data = content.getvalue()
    assert len(data) > 0, "Document content is empty"


def test_delete_document(client: R2RClient):
    # Create a doc to delete
    resp = client.documents.create(raw_text="This is a temporary doc",
                                   run_with_orchestration=False).results
    doc_id = resp.document_id
    del_resp = client.documents.delete(id=doc_id).results
    assert del_resp.success, "Failed to delete document"
    # Verify it's gone
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=doc_id)
    assert exc_info.value.status_code == 404, "Expected 404 after deletion"


def test_delete_document_by_filter(client: R2RClient):
    # Create a doc with unique metadata
    resp = client.documents.create(
        raw_text="Document to be filtered out",
        metadata={
            "to_delete": "yes"
        },
        run_with_orchestration=False,
    ).results
    doc_id = resp.document_id

    filters = {"to_delete": {"$eq": "yes"}}
    del_resp = client.documents.delete_by_filter(filters).results
    assert del_resp.success, "Failed to delete documents by filter"
    # Verify deletion
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=doc_id)
    assert exc_info.value.status_code == 404, (
        "Document still exists after filter-based deletion")


# @pytest.mark.skip(reason="Only if superuser-specific logic is implemented")
def test_list_document_collections(client: R2RClient, test_document):
    # This test assumes the currently logged in user is a superuser
    collections = client.documents.list_collections(id=test_document).results
    assert isinstance(collections,
                      list), ("Document collections list is not a list")


# @pytest.mark.skip(
#     reason="Requires actual entity extraction logic implemented and superuser access"
# )
def test_extract_document(client: R2RClient, test_document):
    time.sleep(10)
    run_resp = client.documents.extract(id=test_document,
                                        run_with_orchestration=False).results
    assert run_resp.message is not None, "No message after extraction run"


# @pytest.mark.skip(reason="Requires entity extraction results present")
def test_list_entities(client: R2RClient, test_document):
    # If no entities extracted yet, this could raise an exception
    try:
        entities = client.documents.list_entities(id=test_document).results
        assert isinstance(entities, list), "Entities response not a list"
    except R2RException as e:
        # Possibly no entities extracted yet
        pytest.skip(f"No entities extracted yet: {str(e)}")


# @pytest.mark.skip(reason="Requires relationship extraction results present")
def test_list_relationships(client: R2RClient, test_document):
    try:
        relationships = client.documents.list_relationships(
            id=test_document).results
        assert isinstance(relationships,
                          list), ("Relationships response not a list")
    except R2RException as e:
        pytest.skip(f"No relationships extracted yet: {str(e)}")


def test_search_documents(client: R2RClient, test_document):
    # Add some delay if indexing takes time
    time.sleep(1)
    query = "Temporary"
    search_results = client.documents.search(query=query,
                                             search_mode="custom",
                                             search_settings={"limit": 5})
    assert search_results.results is not None, "Search results key not found"
    # We cannot guarantee a match, but at least we got a well-formed response
    assert isinstance(search_results.results,
                      list), ("Search results not a list")


def test_list_document_chunks(mutable_client: R2RClient, cleanup_documents):
    temp_user = f"{uuid.uuid4()}@me.com"
    mutable_client.users.create(temp_user, "password")
    mutable_client.users.login(temp_user, "password")

    resp = mutable_client.documents.create(
        chunks=["C1", "C2", "C3"], run_with_orchestration=False).results
    doc_id = cleanup_documents(resp.document_id)
    chunks_resp = mutable_client.documents.list_chunks(id=doc_id)
    results = chunks_resp.results
    assert len(results) == 3, "Expected 3 chunks"
    mutable_client.users.logout()


def test_search_documents_extended(client: R2RClient, cleanup_documents):
    doc_id = cleanup_documents(
        client.documents.create(
            raw_text="Aristotle was a Greek philosopher.",
            run_with_orchestration=False,
        ).results.document_id)

    time.sleep(1)  # If indexing is asynchronous
    search_results = client.documents.search(
        query="Greek philosopher",
        search_mode="basic",
        search_settings={"limit": 1},
    )
    assert search_results.results is not None, (
        "No results key in search response")
    assert len(search_results.results) > 0, "No documents found"


def test_retrieve_document_not_found(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=bad_id)
    assert exc_info.value.status_code == 404, "Wrong error code for not found"


def test_delete_document_non_existent(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.documents.delete(id=bad_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code for delete non-existent")


# @pytest.mark.skip(reason="If your API restricts this endpoint to superusers")
def test_get_document_collections_non_superuser(client):
    # Create a non-superuser client
    non_super_client = R2RClient(client.base_url)
    random_string = str(uuid.uuid4())
    non_super_client.users.create(f"{random_string}@me.com", "password")
    non_super_client.users.login(f"{random_string}@me.com", "password")

    document_id = str(uuid.uuid4())  # Some doc ID
    with pytest.raises(R2RException) as exc_info:
        non_super_client.documents.list_collections(id=document_id)
    assert exc_info.value.status_code == 403, (
        "Expected 403 for non-superuser collections access")


def test_access_document_not_owned(client: R2RClient, cleanup_documents):
    # Create a doc as superuser
    doc_id = cleanup_documents(
        client.documents.create(
            raw_text="Owner doc test",
            run_with_orchestration=False).results.document_id)

    # Now try to access with a non-superuser
    non_super_client = R2RClient(client.base_url)
    random_string = str(uuid.uuid4())
    non_super_client.users.create(f"{random_string}@me.com", "password")
    non_super_client.users.login(f"{random_string}@me.com", "password")

    with pytest.raises(R2RException) as exc_info:
        non_super_client.documents.download(id=doc_id)
    assert exc_info.value.status_code == 403, (
        "Wrong error code for unauthorized access")


def test_list_documents_with_pagination(mutable_client: R2RClient,
                                        cleanup_documents):
    temp_user = f"{uuid.uuid4()}@me.com"
    mutable_client.users.create(temp_user, "password")
    mutable_client.users.login(temp_user, "password")

    for i in range(3):
        cleanup_documents(
            mutable_client.documents.create(
                raw_text=f"Doc {i}",
                run_with_orchestration=False).results.document_id)

    listed = mutable_client.documents.list(limit=2, offset=0)
    results = listed.results
    assert len(results) == 2, "Expected 2 results for paginated listing"


def test_ingest_invalid_chunks(client):
    invalid_chunks = ["Valid chunk", 12345, {"not": "a string"}]
    with pytest.raises(R2RException) as exc_info:
        client.documents.create(chunks=invalid_chunks,
                                run_with_orchestration=False)
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected validation error for invalid chunks"


def test_ingest_too_many_chunks(client):
    excessive_chunks = ["Chunk"] * (1024 * 100 + 1)  # Just over the limit
    with pytest.raises(R2RException) as exc_info:
        client.documents.create(chunks=excessive_chunks,
                                run_with_orchestration=False)
    assert exc_info.value.status_code == 400, (
        "Wrong error code for exceeding max chunks")


def test_delete_by_complex_filter(client: R2RClient, cleanup_documents):
    doc1 = cleanup_documents(
        client.documents.create(
            raw_text="Doc with tag A",
            metadata={
                "tag": "A"
            },
            run_with_orchestration=False,
        ).results.document_id)
    doc2 = cleanup_documents(
        client.documents.create(
            raw_text="Doc with tag B",
            metadata={
                "tag": "B"
            },
            run_with_orchestration=False,
        ).results.document_id)

    filters = {"$or": [{"tag": {"$eq": "A"}}, {"tag": {"$eq": "B"}}]}
    del_resp = client.documents.delete_by_filter(filters).results
    assert del_resp.success, "Complex filter deletion failed"

    # Verify both documents are deleted
    for d_id in [doc1, doc2]:
        with pytest.raises(R2RException) as exc_info:
            client.documents.retrieve(d_id)
        assert exc_info.value.status_code == 404, (
            f"Document {d_id} still exists after deletion")


def test_search_documents_no_match(client: R2RClient, cleanup_documents):
    doc_id = cleanup_documents(
        client.documents.create(
            raw_text="Just a random document",
            metadata={
                "category": "unrelated"
            },
            run_with_orchestration=False,
        ).results.document_id)

    # Search for non-existent category
    search_results = client.documents.search(
        query="nonexistent category",
        search_mode="basic",
        search_settings={
            "filters": {
                "category": {
                    "$eq": "doesnotexist"
                }
            },
            "limit": 10,
        },
    )
    assert search_results.results is not None, "Search missing results key"
    assert len(search_results.results) == 0, "Expected zero results"


import pytest


def test_delete_by_workflow_metadata(client: R2RClient, cleanup_documents):
    """Test deletion by workflow state metadata."""
    # Create test documents with workflow metadata
    random_suffix = uuid.uuid4()
    docs = []

    try:
        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Draft document 1" + str(random_suffix),
                    metadata={
                        "workflow": {
                            "state": "draft",
                            "assignee": "user1",
                            "review_count": 0,
                        }
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Draft document 2" + str(random_suffix),
                    metadata={
                        "workflow": {
                            "state": "draft",
                            "assignee": "user2",
                            "review_count": 1,
                        }
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Published document" + str(random_suffix),
                    metadata={
                        "workflow": {
                            "state": "published",
                            "assignee": "user1",
                            "review_count": 2,
                        }
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        # Delete drafts with no reviews
        filters = {
            "$and": [
                {
                    "metadata.workflow.state": {
                        "$eq": "draft"
                    }
                },
                {
                    "metadata.workflow.review_count": {
                        "$eq": 0
                    }
                },
            ]
        }

        response = client.documents.delete_by_filter(filters).results
        assert response.success

        # Verify first draft is deleted
        with pytest.raises(R2RException) as exc:
            client.documents.retrieve(id=docs[0])
        assert exc.value.status_code == 404

        # Verify other documents still exist
        assert client.documents.retrieve(id=docs[1])
        assert client.documents.retrieve(id=docs[2])

    except Exception:
        raise


def test_delete_by_classification_metadata(client: R2RClient,
                                           cleanup_documents):
    """Test deletion by document classification metadata."""
    docs = []
    try:
        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Confidential document",
                    metadata={
                        "classification": {
                            "level": "confidential",
                            "department": "HR",
                            "retention_years": 7,
                        }
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Public document",
                    metadata={
                        "classification": {
                            "level": "public",
                            "department": "Marketing",
                            "retention_years": 1,
                        }
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        # Delete HR documents with high retention
        filters = {
            "$and": [
                {
                    "classification.department": {
                        "$eq": "HR"
                    }
                },
                {
                    "classification.retention_years": {
                        "$gt": 5
                    }
                },
            ]
        }

        response = client.documents.delete_by_filter(filters).results
        assert response.success

        # Verify confidential HR doc is deleted
        with pytest.raises(R2RException) as exc:
            client.documents.retrieve(id=docs[0])
        assert exc.value.status_code == 404

        # Verify public doc still exists
        assert client.documents.retrieve(id=docs[1])

    except Exception:
        raise


def test_delete_by_version_metadata(client: R2RClient, cleanup_documents):
    """Test deletion by version and status metadata with array conditions."""
    suffix = uuid.uuid4()
    docs = []
    try:
        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Old version document" + str(suffix),
                    metadata={
                        "version_info": {
                            "number": "1.0.0",
                            "status": "deprecated",
                            "tags": ["legacy", "unsupported"],
                        },
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        docs.append(
            cleanup_documents(
                client.documents.create(
                    raw_text="Current version document" + str(suffix),
                    metadata={
                        "version_info": {
                            "number": "2.0.0",
                            "status": "current",
                            "tags": ["stable", "supported"],
                        },
                    },
                    run_with_orchestration=False,
                ).results.document_id))

        # Delete deprecated documents with legacy tag
        filters = {
            "$and": [
                {
                    "metadata.version_info.status": {
                        "$eq": "deprecated"
                    }
                },
                {
                    "metadata.version_info.tags": {
                        "$in": ["legacy"]
                    }
                },
            ]
        }

        response = client.documents.delete_by_filter(filters).results
        assert response.success

        # Verify deprecated doc is deleted
        with pytest.raises(R2RException) as exc:
            client.documents.retrieve(id=docs[0])
        assert exc.value.status_code == 404

        # Verify current doc still exists
        assert client.documents.retrieve(id=docs[1])

    except Exception:
        raise
