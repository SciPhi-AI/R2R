import time
import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and log in as a superuser."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


@pytest.fixture
def test_document(client):
    """Create and yield a test document, then clean up."""
    resp = client.documents.create(
        raw_text="Temporary doc", run_with_orchestration=False
    )
    document_id = resp["results"]["document_id"]
    yield document_id
    # Cleanup
    try:
        client.documents.delete(id=document_id)
    except R2RException:
        pass


def test_create_document_with_file(client):
    resp = client.documents.create(
        file_path="core/examples/data/aristotle.txt",
        run_with_orchestration=False,
    )["results"]
    assert (
        "document_id" in resp and resp["document_id"]
    ), "No document_id returned after file ingestion"
    # Cleanup
    client.documents.delete(id=resp["document_id"])


def test_create_document_with_raw_text(client):
    resp = client.documents.create(
        raw_text="This is raw text content.", run_with_orchestration=False
    )["results"]
    doc_id = resp["document_id"]
    assert doc_id, "No document_id returned after raw text ingestion"
    # Verify retrieval
    retrieved = client.documents.retrieve(id=doc_id)["results"]
    assert (
        retrieved["id"] == doc_id
    ), "Failed to retrieve the ingested raw text document"
    # Cleanup
    client.documents.delete(id=doc_id)


def test_create_document_with_chunks(client):
    resp = client.documents.create(
        chunks=["Chunk one", "Chunk two"], run_with_orchestration=False
    )["results"]
    doc_id = resp["document_id"]
    assert doc_id, "No document_id returned after chunk ingestion"
    retrieved = client.documents.retrieve(id=doc_id)["results"]
    assert (
        retrieved["id"] == doc_id
    ), "Failed to retrieve the chunk-based document"
    # Cleanup
    client.documents.delete(id=doc_id)


def test_create_document_different_modes(client):
    # hi-res mode
    hi_res_resp = client.documents.create(
        raw_text="High resolution doc.",
        ingestion_mode="hi-res",
        run_with_orchestration=False,
    )["results"]
    hi_res_id = hi_res_resp["document_id"]
    assert hi_res_id, "No doc_id returned for hi-res ingestion"
    client.documents.delete(id=hi_res_id)

    # fast mode
    fast_resp = client.documents.create(
        raw_text="Fast mode doc.",
        ingestion_mode="fast",
        run_with_orchestration=False,
    )["results"]
    fast_id = fast_resp["document_id"]
    assert fast_id, "No doc_id returned for fast ingestion"
    client.documents.delete(id=fast_id)


def test_list_documents(client, test_document):
    listed = client.documents.list(offset=0, limit=10)
    results = listed["results"]
    assert isinstance(results, list), "Documents list response is not a list"
    assert len(results) >= 1, "Expected at least one document"
    # test_document is created for this test, so we expect at least that one present.


def test_retrieve_document(client, test_document):
    retrieved = client.documents.retrieve(id=test_document)["results"]
    assert retrieved["id"] == test_document, "Retrieved wrong document"


def test_download_document(client, test_document):
    # For text-only documents, the endpoint returns text as a buffer
    content = client.documents.download(id=test_document)
    assert content, "Failed to download document content"
    data = content.getvalue()
    assert len(data) > 0, "Document content is empty"


def test_delete_document(client):
    # Create a doc to delete
    resp = client.documents.create(
        raw_text="This is a temporary doc", run_with_orchestration=False
    )["results"]
    doc_id = resp["document_id"]
    del_resp = client.documents.delete(id=doc_id)["results"]
    assert del_resp["success"], "Failed to delete document"
    # Verify it's gone
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=doc_id)
    assert exc_info.value.status_code == 404, "Expected 404 after deletion"


def test_delete_document_by_filter(client):
    # Create a doc with unique metadata
    resp = client.documents.create(
        raw_text="Document to be filtered out",
        metadata={"to_delete": "yes"},
        run_with_orchestration=False,
    )["results"]
    doc_id = resp["document_id"]

    filters = {"to_delete": {"$eq": "yes"}}
    del_resp = client.documents.delete_by_filter(filters)["results"]
    assert del_resp["success"], "Failed to delete documents by filter"
    # Verify deletion
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=doc_id)
    assert (
        exc_info.value.status_code == 404
    ), "Document still exists after filter-based deletion"


# @pytest.mark.skip(reason="Only if superuser-specific logic is implemented")
def test_list_document_collections(client, test_document):
    # This test assumes the currently logged in user is a superuser
    collections = client.documents.list_collections(id=test_document)[
        "results"
    ]
    assert isinstance(
        collections, list
    ), "Document collections list is not a list"


# @pytest.mark.skip(
#     reason="Requires actual entity extraction logic implemented and superuser access"
# )
def test_extract_document(client, test_document):
    run_resp = client.documents.extract(
        id=test_document, run_type="run", run_with_orchestration=False
    )["results"]
    assert "message" in run_resp, "No message after extraction run"


# @pytest.mark.skip(reason="Requires entity extraction results present")
def test_list_entities(client, test_document):
    # If no entities extracted yet, this could raise an exception
    try:
        entities = client.documents.list_entities(id=test_document)["results"]
        assert isinstance(entities, list), "Entities response not a list"
    except R2RException as e:
        # Possibly no entities extracted yet
        pytest.skip(f"No entities extracted yet: {str(e)}")


# @pytest.mark.skip(reason="Requires relationship extraction results present")
def test_list_relationships(client, test_document):
    try:
        relationships = client.documents.list_relationships(id=test_document)[
            "results"
        ]
        assert isinstance(
            relationships, list
        ), "Relationships response not a list"
    except R2RException as e:
        pytest.skip(f"No relationships extracted yet: {str(e)}")


def test_search_documents(client, test_document):
    # Add some delay if indexing takes time
    time.sleep(1)
    query = "Temporary"
    search_results = client.documents.search(
        query=query, search_mode="custom", search_settings={"limit": 5}
    )
    assert "results" in search_results, "Search results key not found"
    # We cannot guarantee a match, but at least we got a well-formed response
    assert isinstance(
        search_results["results"], list
    ), "Search results not a list"


def test_list_document_chunks(client):
    temp_user = f"{uuid.uuid4()}@me.com"
    client.users.register(temp_user, "password")
    client.users.login(temp_user, "password")

    resp = client.documents.create(
        chunks=["C1", "C2", "C3"], run_with_orchestration=False
    )["results"]
    doc_id = resp["document_id"]
    chunks_resp = client.documents.list_chunks(id=doc_id)
    results = chunks_resp["results"]
    assert len(results) == 3, "Expected 3 chunks"
    client.documents.delete(id=doc_id)
    client.logout()


def test_search_documents_extended(client):
    doc_id = client.documents.create(
        raw_text="Aristotle was a Greek philosopher.",
        run_with_orchestration=False,
    )["results"]["document_id"]

    time.sleep(1)  # If indexing is asynchronous
    search_results = client.documents.search(
        query="Greek philosopher",
        search_mode="basic",
        search_settings={"limit": 1},
    )
    assert "results" in search_results, "No results key in search response"
    assert len(search_results["results"]) > 0, "No documents found"
    client.documents.delete(id=doc_id)


def test_retrieve_document_not_found(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.documents.retrieve(id=bad_id)
    assert exc_info.value.status_code == 404, "Wrong error code for not found"


def test_delete_document_non_existent(client):
    bad_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.documents.delete(id=bad_id)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for delete non-existent"


# @pytest.mark.skip(reason="If your API restricts this endpoint to superusers")
def test_get_document_collections_non_superuser(client):
    # Create a non-superuser client
    non_super_client = R2RClient(client.base_url)
    random_string = str(uuid.uuid4())
    non_super_client.users.register(f"{random_string}@me.com", "password")
    non_super_client.users.login(f"{random_string}@me.com", "password")

    document_id = str(uuid.uuid4())  # Some doc ID
    with pytest.raises(R2RException) as exc_info:
        non_super_client.documents.list_collections(id=document_id)
    assert (
        exc_info.value.status_code == 403
    ), "Expected 403 for non-superuser collections access"


def test_access_document_not_owned(client):
    # Create a doc as superuser
    doc_id = client.documents.create(
        raw_text="Owner doc test", run_with_orchestration=False
    )["results"]["document_id"]

    # Now try to access with a non-superuser
    non_super_client = R2RClient(client.base_url)
    random_string = str(uuid.uuid4())
    non_super_client.users.register(f"{random_string}@me.com", "password")
    non_super_client.users.login(f"{random_string}@me.com", "password")

    with pytest.raises(R2RException) as exc_info:
        non_super_client.documents.download(id=doc_id)
    assert (
        exc_info.value.status_code == 403
    ), "Wrong error code for unauthorized access"

    # Cleanup
    client.documents.delete(id=doc_id)


def test_list_documents_with_pagination(client):
    doc_ids = []
    for i in range(5):
        resp = client.documents.create(
            raw_text=f"Doc {i}", run_with_orchestration=False
        )["results"]
        doc_ids.append(resp["document_id"])

    listed = client.documents.list(limit=2, offset=0)
    results = listed["results"]
    assert len(results) == 2, "Expected 2 results for paginated listing"

    # Cleanup
    for d in doc_ids:
        client.documents.delete(id=d)


def test_ingest_invalid_chunks(client):
    invalid_chunks = ["Valid chunk", 12345, {"not": "a string"}]
    with pytest.raises(R2RException) as exc_info:
        client.documents.create(
            chunks=invalid_chunks, run_with_orchestration=False
        )
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected validation error for invalid chunks"


def test_ingest_too_many_chunks(client):
    excessive_chunks = ["Chunk"] * (1024 * 100 + 1)  # Just over the limit
    with pytest.raises(R2RException) as exc_info:
        client.documents.create(
            chunks=excessive_chunks, run_with_orchestration=False
        )
    assert (
        exc_info.value.status_code == 400
    ), "Wrong error code for exceeding max chunks"


def test_delete_by_complex_filter(client):
    doc1 = client.documents.create(
        raw_text="Doc with tag A",
        metadata={"tag": "A"},
        run_with_orchestration=False,
    )["results"]["document_id"]
    doc2 = client.documents.create(
        raw_text="Doc with tag B",
        metadata={"tag": "B"},
        run_with_orchestration=False,
    )["results"]["document_id"]

    filters = {"$or": [{"tag": {"$eq": "A"}}, {"tag": {"$eq": "B"}}]}
    del_resp = client.documents.delete_by_filter(filters)["results"]
    assert del_resp["success"], "Complex filter deletion failed"

    # Verify both documents are deleted
    for d_id in [doc1, doc2]:
        with pytest.raises(R2RException) as exc_info:
            client.documents.retrieve(d_id)
        assert (
            exc_info.value.status_code == 404
        ), f"Document {d_id} still exists after deletion"


def test_search_documents_no_match(client):
    doc_id = client.documents.create(
        raw_text="Just a random document",
        metadata={"category": "unrelated"},
        run_with_orchestration=False,
    )["results"]["document_id"]

    # Search for non-existent category
    search_results = client.documents.search(
        query="nonexistent category",
        search_mode="basic",
        search_settings={
            "filters": {"category": {"$eq": "doesnotexist"}},
            "limit": 10,
        },
    )
    assert "results" in search_results, "Search missing results key"
    assert len(search_results["results"]) == 0, "Expected zero results"

    # Cleanup
    client.documents.delete(id=doc_id)
