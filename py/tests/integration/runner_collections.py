import argparse
import sys
import time
import uuid

from r2r import R2RClient, R2RException


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def create_test_document(raw_text="Test doc for collections"):
    # Create a document using documents SDK
    create_resp = client.documents.create(
        raw_text=raw_text, run_with_orchestration=False
    )["results"]
    doc_id = create_resp["document_id"]
    assert_http_error(
        doc_id is not None,
        "Failed to create test document for collection tests",
    )
    return doc_id


def delete_test_document(doc_id):
    delete_resp = client.documents.delete(id=doc_id)["results"]
    assert_http_error(delete_resp["success"], "Failed to delete test document")


def test_create_collection():
    print("Testing: Create collection")
    resp = client.collections.create(
        name="Test Collection", description="A sample collection for testing"
    )
    coll = resp["results"]
    global TEST_COLLECTION_ID
    TEST_COLLECTION_ID = coll["id"]
    assert_http_error(
        TEST_COLLECTION_ID is not None, "No collection_id returned"
    )
    print("Create collection test passed")
    print("~" * 100)


def test_list_collections():
    print("Testing: List collections")
    listed = client.collections.list(limit=10, offset=0)
    results = listed["results"]
    assert_http_error(
        len(results) >= 1, "Expected at least one collection, none found"
    )
    print("List collections test passed")
    print("~" * 100)


def test_retrieve_collection():
    print("Testing: Retrieve collection")
    listed = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed[0]["id"]
    retrieved = client.collections.retrieve(coll_id)["results"]
    assert_http_error(
        retrieved["id"] == coll_id, "Retrieved wrong collection ID"
    )
    print("Retrieve collection test passed")
    print("~" * 100)


def test_update_collection():
    print("Testing: Update collection")
    updated_name = "Updated Test Collection"
    updated_desc = "Updated description"
    listed = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed[0]["id"]
    updated = client.collections.update(
        coll_id, name=updated_name, description=updated_desc
    )["results"]
    assert_http_error(
        updated["name"] == updated_name, "Collection name not updated"
    )
    assert_http_error(
        updated["description"] == updated_desc,
        "Collection description not updated",
    )
    print("Update collection test passed")
    print("~" * 100)


def test_add_document_to_collection():
    print("Testing: Add document to collection")
    # global TEST_DOCUMENT_ID
    TEST_DOCUMENT_ID = create_test_document("Doc to add to collection")

    listed_collections = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed_collections[0]["id"]
    print("TEST_COLLECTION_ID = ", coll_id)

    resp = client.collections.add_document(coll_id, TEST_DOCUMENT_ID)
    # Expect a success message or similar result
    # Check no exception thrown
    print("Add document to collection test passed")
    print("~" * 100)


def test_list_documents_in_collection():
    print("Testing: List documents in collection")
    listed_collections = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed_collections[0]["id"]
    docs_in_collection = client.collections.list_documents(coll_id)["results"]

    listed_documents = client.documents.list(limit=10, offset=0)["results"]
    document_id = listed_documents[0]["id"]
    found = any(doc["id"] == document_id for doc in docs_in_collection)
    # Expect to find the document we just added
    # found = any(doc["document_id"] == TEST_DOCUMENT_ID for doc in results)
    assert_http_error(found, "Added document not found in collection")
    print("List documents in collection test passed")
    print("~" * 100)


def test_remove_document_from_collection():
    print("Testing: Remove document from collection")
    listed_collections = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed_collections[0]["id"]

    listed_documents = client.documents.list(limit=10, offset=0)["results"]
    document_id = listed_documents[0]["id"]

    resp = client.collections.remove_document(coll_id, document_id)
    # Verify it was removed
    docs_in_collection = client.collections.list_documents(coll_id)["results"]
    found = any(
        doc["document_id"] == document_id for doc in docs_in_collection
    )
    assert_http_error(
        not found, "Document still present in collection after removal"
    )
    # Cleanup doc
    delete_test_document(document_id)
    print("Remove document from collection test passed")
    print("~" * 100)


# If you had user management and separate user IDs, you would test add_user/remove_user here.


def test_delete_collection():
    print("Testing: Delete collection")
    listed_collections = client.collections.list(limit=10, offset=0)["results"]
    coll_id = listed_collections[0]["id"]

    resp = client.collections.delete(coll_id)
    # Verify deletion
    # Attempt to retrieve should fail now
    try:
        client.collections.retrieve(coll_id)
        print("Expected error retrieving deleted collection, got none.")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            e.status_code == 404,
            "Wrong error code retrieving deleted collection",
        )
    print("Delete collection test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R SDK Collections Integration Tests"
    )
    parser.add_argument("test_function", help="Test function to run")
    parser.add_argument(
        "--base-url",
        default="http://localhost:7272",
        help="Base URL for the R2R client",
    )
    args = parser.parse_args()

    global client, TEST_COLLECTION_ID, TEST_DOCUMENT_ID
    TEST_COLLECTION_ID = None
    TEST_DOCUMENT_ID = None
    client = create_client(args.base_url)

    test_function = args.test_function
    globals()[test_function]()
