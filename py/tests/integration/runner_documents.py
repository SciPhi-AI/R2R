import argparse
import sys
import time
import uuid

from r2r import R2RClient, R2RException

# ---------------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------------


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def create_test_document(
    file_path=None,
    raw_text=None,
    chunks=None,
    ingestion_mode="custom",
    run_with_orchestration=False,
    metadata=None,
    collection_ids=None,
):
    # This helper function creates a document using the specified parameters.
    # Returns the created document_id.
    args = []
    if file_path:
        args.extend(["--file-path", file_path])
    if raw_text:
        args.extend(["--raw-text", raw_text])
    if chunks:
        args.extend(["--chunks", str(chunks)])
    if metadata:
        args.extend(["--metadata", str(metadata)])
    if collection_ids:
        args.extend(["--collection-ids", str(collection_ids)])

    # We'll just call the API directly:
    create_response = client.documents.create(
        file_path=file_path,
        raw_text=raw_text,
        chunks=chunks,
        ingestion_mode=ingestion_mode,
        run_with_orchestration=run_with_orchestration,
        metadata=metadata,
        collection_ids=collection_ids,
    )["results"]

    if not create_response["document_id"]:
        print("Failed to create test document.")
        sys.exit(1)
    return create_response["document_id"]


def delete_test_document(document_id):
    delete_resp = client.documents.delete(id=document_id)["results"]
    if not delete_resp["success"]:
        print("Failed to delete test document:", document_id)
        sys.exit(1)


def compare_result_fields(result, expected_fields):
    for field, expected_value in expected_fields.items():
        if callable(expected_value):
            if not expected_value(result[field]):
                print(f"Test failed: Incorrect {field}")
                print(f"Expected {field} to satisfy the condition")
                print(f"Actual {field}:", result[field])
                sys.exit(1)
        else:
            if result[field] != expected_value:
                print(f"Test failed: Incorrect {field}")
                print(f"Expected {field}:", expected_value)
                print(f"Actual {field}:", result[field])
                sys.exit(1)


# ---------------------------------------------------------------------------------
# Original Tests
# ---------------------------------------------------------------------------------


def test_create_document():
    print("Testing: Ingest sample file SDK")
    file_path = "core/examples/data/aristotle.txt"
    create_response = client.documents.create(
        file_path=file_path, run_with_orchestration=False
    )

    if not create_response["results"]:
        print("Ingestion test failed")
        sys.exit(1)
    print("Ingestion successful")
    print("~" * 100)


def test_list_documents():
    documents = client.documents.list()["results"]
    sample_document = {
        "id": "db02076e-989a-59cd-98d5-e24e15a0bd27",
        "title": "aristotle.txt",
        "document_type": "txt",
        "ingestion_status": "success",
        "extraction_status": "pending",
        "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
    }

    if not any(
        all(doc.get(k) == v for k, v in sample_document.items())
        for doc in documents
    ):
        for doc in documents:
            print(doc)
            for k, v in sample_document.items():
                print(doc.get(k))
                print(v)
        sys.exit(1)
    print("Document overview test passed")
    print("~" * 100)


def test_retrieve_document():
    print("Testing: Retrieve a specific document")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    doc = client.documents.retrieve(id=document_id)["results"]
    if not doc["id"] == document_id:
        print("Failed to retrieve the correct document.")
        sys.exit(1)
    print("Retrieve document test passed")
    print("~" * 100)


def test_download_document():
    print("Testing: Download document content")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    content = client.documents.download(id=document_id)
    if not content:
        print("Failed to download document content.")
        sys.exit(1)

    data = content.getvalue()
    print("Content length:", len(data))
    print("Download document test passed")
    print("~" * 100)


def test_delete_document():
    print("Testing: Delete a specific document")
    # First create a doc to delete
    create_resp = client.documents.create(
        raw_text="This is a temporary doc", run_with_orchestration=False
    )["results"]
    print("Created document:", create_resp)
    doc_id = create_resp["document_id"]
    delete_resp = client.documents.delete(id=doc_id)["results"]
    if not delete_resp["success"]:
        print("Failed to delete the document.")
        sys.exit(1)
    # Optionally verify it's gone:
    try:
        result = client.documents.retrieve(doc_id)
        print("retrieve result:", result)
        print("Document still exists after deletion.")
        sys.exit(1)
    except R2RException as e:
        if e.status_code != 404:
            print("Unexpected error after deletion:", e)
            sys.exit(1)
    print("Delete document test passed")
    print("~" * 100)


def test_delete_document_by_filter():
    print("Testing: Delete documents by filter")
    # Create a doc with a unique metadata field to filter by
    unique_meta = {"to_delete": "yes"}
    create_resp = client.documents.create(
        raw_text="Document to be filtered out",
        metadata=unique_meta,
        run_with_orchestration=False,
    )["results"]
    doc_id = create_resp["document_id"]

    filters = {"to_delete": {"$eq": "yes"}}
    del_resp = client.documents.delete_by_filter(filters)["results"]
    if not del_resp["success"]:
        print("Failed to delete documents by filter.")
        sys.exit(1)
    # Verify deletion:
    try:
        client.documents.retrieve(doc_id)
        print("Document still exists after filter-based deletion.")
        sys.exit(1)
    except R2RException as e:
        if e.status_code != 404:
            print("Unexpected error after filter-based deletion:", e)
            sys.exit(1)
    print("Delete by filter test passed")
    print("~" * 100)


def test_list_document_collections():
    print("Testing: List collections containing a document (superuser-only)")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    collections = client.documents.list_collections(id=document_id)["results"]
    if not isinstance(collections, list):
        print("Failed to list document collections.")
        sys.exit(1)
    print("List document collections test passed")
    print("~" * 100)


def test_extract_document():
    print("Testing: Extract entities and relationships")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    run_resp = client.documents.extract(
        id=document_id, run_type="run", run_with_orchestration=False
    )["results"]
    if "message" not in run_resp:
        print("Failed to run entity extraction.")
        sys.exit(1)
    print("Entity extraction test passed")
    print("~" * 100)


def test_list_entities():
    print("Testing: List entities for a document")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    try:
        entities = client.documents.list_entities(id=document_id)["results"]
    except R2RException as e:
        # possibly no entities extracted yet
        print("No entities extracted yet:", str(e))
        # Not failing the test here since original code expects possibly no entities
        print("List entities test passed (no entities extracted yet)")
        return

    if not isinstance(entities, list):
        print("Failed to list entities.")
        sys.exit(1)

    print("List entities test passed")
    print("~" * 100)


def test_list_relationships():
    print("Testing: List relationships for a document")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    try:
        relationships = client.documents.list_relationships(id=document_id)[
            "results"
        ]
    except R2RException as e:
        print("No relationships extracted yet:", str(e))
        print("List relationships test passed (no relationships extracted)")
        return

    if not isinstance(relationships, list):
        print("Failed to list relationships.")
        sys.exit(1)
    print("List relationships test passed")
    print("~" * 100)


def test_search_documents():
    print("Testing: Search documents")
    query = "Aristotle philosophy"
    search_results = client.documents.search(
        query=query, search_mode="custom", search_settings={"limit": 5}
    )
    if "results" not in search_results:
        print("Failed to search documents.")
        sys.exit(1)
    print("Document search test passed")
    print("~" * 100)


# ---------------------------------------------------------------------------------
# New Tests
# ---------------------------------------------------------------------------------


def test_create_document_with_chunks():
    print("Testing: Create document with chunks")
    doc_id = create_test_document(chunks=["Chunk one", "Chunk two"])
    # Verify retrieval
    doc = client.documents.retrieve(id=doc_id)["results"]
    assert_http_error(doc["id"] == doc_id, "Chunks ingestion failed")
    print("Document with chunks created successfully")
    delete_test_document(doc_id)
    print("~" * 100)


def test_create_document_with_raw_text():
    print("Testing: Create document with raw_text")
    doc_id = create_test_document(raw_text="This is raw text content.")
    doc = client.documents.retrieve(id=doc_id)["results"]
    assert_http_error(doc["id"] == doc_id, "Raw text ingestion failed")
    print("Document with raw text created successfully")
    delete_test_document(doc_id)
    print("~" * 100)


def test_create_document_different_modes():
    print("Testing: Create document with different ingestion modes")
    # hi-res mode
    doc_id = create_test_document(
        raw_text="High resolution doc.", ingestion_mode="hi-res"
    )
    doc = client.documents.retrieve(id=doc_id)["results"]
    assert_http_error(doc["id"] == doc_id, "Hi-res ingestion failed")
    delete_test_document(doc_id)

    # fast mode
    doc_id = create_test_document(
        raw_text="Fast mode doc.", ingestion_mode="fast"
    )
    doc = client.documents.retrieve(id=doc_id)["results"]
    assert_http_error(doc["id"] == doc_id, "Fast ingestion failed")
    delete_test_document(doc_id)

    print("Different modes test passed")
    print("~" * 100)


def test_list_document_chunks():
    print("Testing: List document chunks")
    doc_id = create_test_document(chunks=["C1", "C2", "C3"])
    chunks_resp = client.documents.list_chunks(id=doc_id)
    assert_http_error("results" in chunks_resp, "Chunks listing failed")
    results = chunks_resp["results"]
    assert_http_error(len(results) == 3, "Expected 3 chunks")
    delete_test_document(doc_id)
    print("Listing chunks test passed")
    print("~" * 100)


def test_search_documents_extended():
    print("Testing: Document search with different settings")
    # Ensure we have a searchable doc
    doc_id = create_test_document(
        raw_text="Aristotle was a Greek philosopher."
    )
    # Wait a bit for indexing, if needed
    time.sleep(1)

    # Custom search with filters maybe?
    search_results = client.documents.search(
        query="Greek philosopher",
        search_mode="basic",  # test a different mode
        search_settings={"limit": 1},
    )
    assert_http_error("results" in search_results, "Search failed")
    assert_http_error(len(search_results["results"]) > 0, "No results found")
    delete_test_document(doc_id)
    print("Extended search test passed")
    print("~" * 100)


# def test_extract_document_estimate():
#     print("Testing: Extract document estimate")
#     # Use the known test document
#     document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
#     resp = client.documents.extract(id=document_id, run_type="estimate")
#     assert_http_error("estimate" in resp, "No estimate returned")
#     print("Estimate test passed")
#     print("~" * 100)


def test_extract_document_unauthorized():
    print("Testing: Extract document as non-superuser (expected fail)")
    # We'll pretend client_non_superuser is a non-superuser client
    # In reality, you'd do something like client_non_superuser.login("user", "pass")
    client_non_superuser = create_client("http://localhost:7272")
    random_string = str(uuid.uuid4())
    client_non_superuser.users.create(f"{random_string}@me.com", "password")
    client_non_superuser.users.login(f"{random_string}@me.com", "password")

    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    try:
        result = client_non_superuser.documents.extract(
            id=document_id, run_type="run"
        )
        print("resul;t = ", result)
        print("Expected a 403 error for non-superuser extraction, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403,
            "Wrong error code for unauthorized extraction",
        )
    print("Unauthorized extraction test passed")
    print("~" * 100)


def test_retrieve_document_not_found():
    print("Testing: Retrieve non-existent document")
    bad_id = str(uuid.uuid4())
    try:
        client.documents.retrieve(id=bad_id)
        print("Expected 404 for non-existent document, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Wrong error code for not found"
        )
    print("Retrieve non-existent document test passed")
    print("~" * 100)


def test_delete_document_non_existent():
    print("Testing: Delete non-existent document")
    bad_id = str(uuid.uuid4())
    try:
        resp = client.documents.delete(id=bad_id)
        # If the API returns success=True even for non-existent, this might be a no-op
        # Check expected behavior. If expecting a 404:
        print("Expected an error deleting non-existent document.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Wrong error code for delete non-existent"
        )
    print("Delete non-existent document test passed")
    print("~" * 100)


def test_get_document_collections_non_superuser():
    print("Testing: Collections endpoint as non-superuser")
    client_non_superuser = create_client("http://localhost:7272")
    random_string = str(uuid.uuid4())
    client_non_superuser.users.create(f"{random_string}@me.com", "password")
    client_non_superuser.users.login(f"{random_string}@me.com", "password")

    # Without superuser perms, should fail
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    try:
        client_non_superuser.documents.list_collections(id=document_id)
        print("Expected 403 for non-superuser collections listing, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403,
            "Wrong error code for non-superuser collections",
        )
    print("Non-superuser collections test passed")
    print("~" * 100)


def test_access_document_not_owned():
    print(
        "Testing: Access a document not owned by user and not in accessible collections"
    )
    # Create a doc as superuser
    doc_id = create_test_document(raw_text="Owner doc 11")
    # Now try to retrieve with a non-superuser client
    client_non_superuser = create_client("http://localhost:7272")
    random_string = str(uuid.uuid4())
    client_non_superuser.users.create(f"{random_string}@me.com", "password")
    client_non_superuser.users.login(f"{random_string}@me.com", "password")

    try:
        client_non_superuser.documents.download(id=doc_id)
        print("Expected 403 for accessing not-owned doc, got success.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403, "Wrong error code for unauthorized access"
        )
    delete_test_document(doc_id)
    print("Access not-owned doc test passed")
    print("~" * 100)


def test_list_documents_with_pagination():
    print("Testing: List documents with pagination")
    # Create multiple docs
    doc_ids = [create_test_document(raw_text=f"Doc {i}") for i in range(5)]
    listed = client.documents.list(limit=2, offset=0)
    results = listed["results"]
    assert_http_error(
        len(results) == 2, "Expected 2 results in paginated listing"
    )
    # Cleanup
    for d in doc_ids:
        delete_test_document(d)
    print("Pagination test passed")
    print("~" * 100)


def test_ingest_invalid_chunks():
    print("Testing: Ingestion with invalid chunk data")

    # Attempt to create a document with invalid chunk data (e.g., a list containing non-string elements)
    invalid_chunks = ["Valid chunk", 12345, {"not": "a string"}]

    try:
        client.documents.create(
            chunks=invalid_chunks, run_with_orchestration=False
        )
        print("Expected validation error for invalid chunks, got none.")
        sys.exit(1)
    except R2RException as e:
        # Expecting a 422 or 400 error for invalid input
        assert_http_error(
            e.status_code in [400, 422],
            "Wrong error code for invalid chunks ingestion",
        )

    print("Ingestion with invalid chunks data test passed")
    print("~" * 100)


def test_ingest_too_many_chunks():
    print("Testing: Ingestion with too many chunks")
    # Assume MAX_CHUNKS_PER_REQUEST is 100000 as per your code snippet, adjust if different
    excessive_chunks = ["Chunk"] * (
        1024 * 100 + 1
    )  # Just one more than allowed

    try:
        client.documents.create(
            chunks=excessive_chunks, run_with_orchestration=False
        )
        print("Expected error for exceeding max chunks, got none.")
        sys.exit(1)
    except R2RException as e:
        # Expecting a 400 error given the code snippet
        assert_http_error(
            e.status_code == 400, "Wrong error code for exceeding max chunks"
        )

    print("Ingestion with too many chunks test passed")
    print("~" * 100)


def test_delete_by_complex_filter():
    print("Testing: Delete by filter with complex conditions")

    # Create documents with varying metadata
    doc1_id = client.documents.create(
        raw_text="Doc with tag A",
        metadata={"tag": "A"},
        run_with_orchestration=False,
    )["results"]["document_id"]
    doc2_id = client.documents.create(
        raw_text="Doc with tag B",
        metadata={"tag": "B"},
        run_with_orchestration=False,
    )["results"]["document_id"]

    # Complex filter: delete documents that have tag = "A" OR tag = "B"
    # This depends on your filter schema, assuming something like:
    # {"$or": [{"tag": {"$eq": "A"}}, {"tag": {"$eq": "B"}}]}
    filters = {"$or": [{"tag": {"$eq": "A"}}, {"tag": {"$eq": "B"}}]}
    del_resp = client.documents.delete_by_filter(filters)["results"]
    assert_http_error(del_resp["success"], "Complex filter deletion failed")

    # Verify both documents are deleted
    for d_id in [doc1_id, doc2_id]:
        try:
            client.documents.retrieve(d_id)
            print(f"Document {d_id} still exists after filter-based deletion.")
            sys.exit(1)
        except R2RException as e:
            assert_http_error(
                e.status_code == 404, "Wrong error after filter-based deletion"
            )

    print("Delete by complex filter test passed")
    print("~" * 100)


def test_search_documents_no_match():
    print("Testing: Search documents with filters that return no results")

    # Create a doc that doesn't match our search criteria
    doc_id = client.documents.create(
        raw_text="Just a random document",
        metadata={"category": "unrelated"},
        run_with_orchestration=False,
    )["results"]["document_id"]

    # Use a filter that doesn't match this doc
    # Example: Searching for documents with category = "nonexistent"
    search_results = client.documents.search(
        query="nonexistent category",
        search_mode="basic",
        search_settings={
            "filters": {"category": {"$eq": "doesnotexist"}},
            "limit": 10,
        },
    )

    assert_http_error(
        "results" in search_results, "Search response missing results key"
    )
    assert_http_error(
        len(search_results["results"]) == 0,
        "Expected zero results for unmatched filter",
    )

    # Cleanup
    client.documents.delete(id=doc_id)
    print("Search documents no-match test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="R2R SDK Integration Tests")
    parser.add_argument("test_function", help="Test function to run")
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    global client
    client = create_client(args.base_url)

    test_function = args.test_function
    globals()[test_function]()
