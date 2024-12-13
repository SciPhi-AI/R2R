import argparse
import sys
import time
import uuid

from r2r import R2RClient, R2RException


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def create_document_with_chunks(
    chunks=["Aristotle chunk", "Philosopher chunk"],
    run_with_orchestration=False,
):
    """
    Creates a document by passing chunks directly to the documents router.
    Returns (document_id, chunks_list) after ingestion.
    """
    create_response = client.documents.create(
        chunks=chunks, run_with_orchestration=run_with_orchestration
    )["results"]
    document_id = create_response["document_id"]
    assert_http_error(document_id is not None, "No document_id returned")

    # Wait a moment if needed to ensure ingestion pipeline completes
    # Depending on your setup, you may need to wait or check statuses
    time.sleep(1)

    # Now fetch the chunks of this document
    list_chunks_resp = client.documents.list_chunks(id=document_id)
    doc_chunks = list_chunks_resp["results"]
    assert_http_error(
        len(doc_chunks) == len(chunks), "Number of chunks does not match"
    )
    return document_id, doc_chunks


def delete_test_document(document_id):
    delete_resp = client.documents.delete(id=document_id)["results"]
    if not delete_resp["success"]:
        print("Failed to delete test document:", document_id)
        sys.exit(1)


# Test functions now rely on documents and their chunks


def test_create_and_list_chunks():
    print("Testing: Create document and list its chunks")
    doc_id, doc_chunks = create_document_with_chunks(
        ["Hello chunk", "World chunk"]
    )
    assert_http_error(
        len(doc_chunks) == 2, "Expected 2 chunks in the document"
    )
    print("Create document and list chunks test passed")
    delete_test_document(doc_id)
    print("~" * 100)


def test_retrieve_chunk():
    print("Testing: Retrieve a specific chunk")
    doc_id, doc_chunks = create_document_with_chunks(["To retrieve"])
    chunk_id = doc_chunks[0]["id"]
    retrieved = client.chunks.retrieve(id=chunk_id)["results"]
    assert_http_error(retrieved["id"] == chunk_id, "Retrieved wrong chunk ID")
    assert_http_error(
        retrieved["text"] == "To retrieve", "Chunk text mismatch"
    )
    print("Retrieve chunk test passed")
    delete_test_document(doc_id)
    print("~" * 100)


def test_update_chunk():
    print("Testing: Update a chunk")
    doc_id, doc_chunks = create_document_with_chunks(["Original text"])
    chunk_id = doc_chunks[0]["id"]
    updated = client.chunks.update(
        {"id": chunk_id, "text": "Updated text", "metadata": {"version": 2}}
    )["results"]
    assert_http_error(
        updated["text"] == "Updated text", "Chunk text did not update"
    )
    assert_http_error(
        updated["metadata"]["version"] == 2, "Chunk metadata not updated"
    )

    # Verify retrieval after update
    retrieved = client.chunks.retrieve(id=chunk_id)["results"]
    assert_http_error(
        retrieved["text"] == "Updated text",
        "Updated chunk text not correct on retrieval",
    )
    print("Update chunk test passed")
    delete_test_document(doc_id)
    print("~" * 100)


def test_delete_chunk():
    print("Testing: Delete chunk")
    doc_id, doc_chunks = create_document_with_chunks(
        ["To be deleted", "Another chunk"]
    )
    chunk_id = doc_chunks[0]["id"]
    del_resp = client.chunks.delete(id=chunk_id)["results"]
    assert_http_error(del_resp["success"], "Chunk deletion failed")

    # Verify it's gone
    try:
        result = client.chunks.retrieve(id=chunk_id)
        print("result = ", result)

        print("Expected 404 for deleted chunk, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404,
            "Wrong error code for non-existent chunk retrieval",
        )
    print("Delete chunk test passed")
    delete_test_document(doc_id)
    print("~" * 100)


def test_search_chunks():
    print("Testing: Search chunks")
    doc_id, doc_chunks = create_document_with_chunks(
        ["Aristotle reference", "Another piece of text"]
    )
    time.sleep(1)  # Wait for indexing if needed

    # Search for "Aristotle"
    results = client.chunks.search(
        query="Aristotle", search_settings={"limit": 5}
    )["results"]
    assert_http_error(
        len(results) > 0, "No search results found for 'Aristotle'"
    )

    delete_test_document(doc_id)
    print("Search chunks test passed")
    print("~" * 100)


def test_list_chunks_with_pagination():
    print("Testing: List chunks with pagination")
    doc_id, doc_chunks = create_document_with_chunks(
        ["C1", "C2", "C3", "C4", "C5"]
    )
    # We have 5 chunks now, let's list with limit=2
    listed = client.chunks.list(limit=2, offset=0)
    results = listed["results"]
    assert_http_error(
        len(results) == 2, "Expected 2 results on first paginated call"
    )

    delete_test_document(doc_id)
    print("Pagination test passed")
    print("~" * 100)


def test_retrieve_chunk_not_found():
    print("Testing: Retrieve non-existent chunk")
    bad_id = str(uuid.uuid4())
    try:
        client.chunks.retrieve(id=bad_id)
        print("Expected 404 for non-existent chunk, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404, "Wrong error code for not found chunk"
        )
    print("Retrieve non-existent chunk test passed")
    print("~" * 100)


def test_unauthorized_chunk_access():
    print("Testing: Unauthorized chunk access")
    # Create doc as superuser (client assumed superuser)
    doc_id, doc_chunks = create_document_with_chunks(["Owner's chunk"])
    chunk_id = doc_chunks[0]["id"]

    # Simulate non-owner client (no auth)
    client_non_owner = create_client("http://localhost:7272")
    random_string = str(uuid.uuid4())
    client_non_owner.users.create(f"{random_string}@me.com", "password")
    client_non_owner.users.login(f"{random_string}@me.com", "password")

    try:
        client_non_owner.chunks.retrieve(id=chunk_id)
        print("Expected 403 for unauthorized access, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 403, "Wrong error code for unauthorized access"
        )

    delete_test_document(doc_id)
    print("Unauthorized chunk access test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R SDK Chunks Integration Tests"
    )
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
