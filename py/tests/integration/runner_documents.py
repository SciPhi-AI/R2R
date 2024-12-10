import argparse
import sys
import time

from r2r import R2RClient, R2RException


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
    # If it’s text:
    # print("Content (as text):", data.decode("utf-8", errors="replace"))

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

    # Use a filter that matches this newly created doc
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
    # Assume we have superuser auth and a known document_id
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    collections = client.documents.list_collections(id=document_id)["results"]
    # Basic check: ensure we got a list
    if not isinstance(collections, list):
        print("Failed to list document collections.")
        sys.exit(1)
    print("List document collections test passed")
    print("~" * 100)


def test_extract_document():
    print("Testing: Extract entities and relationships")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    # First just get an estimate:
    # estimate_resp = client.documents.extract(id=document_id, run_type="estimate")
    # if "estimate" not in estimate_resp:
    #     print("Failed to get entity extraction estimate.")
    #     sys.exit(1)
    # print("Entity extraction estimate retrieved successfully")

    # Then actually run extraction (requires superuser and doc readiness):
    run_resp = client.documents.extract(
        id=document_id, run_type="run", run_with_orchestration=False
    )["results"]
    # Just check for a message:
    if "message" not in run_resp:
        print("Failed to run entity extraction.")
        sys.exit(1)
    print("Entity extraction test passed")
    print("~" * 100)


def test_list_entities():
    print("Testing: List entities for a document")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    entities = client.documents.list_entities(id=document_id)["results"]
    # Basic check: we got a list back. Entities might be empty if not extracted yet, but we can still check format.
    if not isinstance(entities, list):
        print("Failed to list entities.")
        sys.exit(1)

    if len(entities) == 0:
        print("List entities test passed (no entities extracted yet)")
        raise R2RException("No entities extracted yet")

    print("List entities test passed")
    print("~" * 100)


def test_list_relationships():
    print("Testing: List relationships for a document")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"
    relationships = client.documents.list_relationships(id=document_id)[
        "results"
    ]
    # Basic check: ensure it's a list
    if not isinstance(relationships, list):
        print("Failed to list relationships.")
        sys.exit(1)

    if len(relationships) == 0:
        print(
            "List relationships test passed (no relationships extracted yet)"
        )
        raise R2RException("No relationships extracted yet")

    print("List relationships test passed")
    print("~" * 100)


def test_search_documents():
    print("Testing: Search documents")
    query = "Aristotle philosophy"
    search_results = client.documents.search(
        query=query, search_mode="custom", search_settings={"limit": 5}
    )
    # Basic check: ensure we got some results back
    if "results" not in search_results:
        print("Failed to search documents.")
        sys.exit(1)
    print("Document search test passed")
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


# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("Please specify a test function to run")
#         sys.exit(1)

#     test_function = sys.argv[1]
#     globals()[test_function]()
