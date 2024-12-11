import argparse
import sys
import uuid

from r2r import R2RClient, R2RException


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def test_create_and_get_index():
    print("Testing: Create and get index")
    index_name = "test_index_" + str(uuid.uuid4())[:8]

    # Create an HNSW index configuration
    config = {
        "table_name": "chunks",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {"m": 16, "ef_construction": 64, "ef": 40},
        "index_name": index_name,
        "index_column": "vec",
        "concurrently": True,
    }

    # Create the index
    create_resp = client.indices.create(
        config=config, run_with_orchestration=True
    )["results"]

    assert_http_error(
        "message" in create_resp, "No message in create response"
    )

    # Get the index details
    get_resp = client.indices.retrieve(
        index_name=index_name, table_name="chunks"
    )["results"]

    assert_http_error("index" in get_resp, "No index in get response")
    assert_http_error(
        get_resp["index"]["name"] == index_name, "Index name mismatch"
    )

    print("Create and get index test passed")
    print("~" * 100)


def test_list_indices():
    print("Testing: List indices")
    resp = client.indices.list(limit=5)["results"]
    assert_http_error("indices" in resp, "No indices field in response")
    print("List indices test passed")
    print("~" * 100)


# def test_list_indices_with_filters():
#     print("Testing: List indices with filters")
#     filters = {"table_name": {"$eq": "chunks"}}
#     resp = client.indices.list(
#         filters=filters,
#         limit=5
#     )["results"]

#     assert_http_error("indices" in resp, "No indices field in filtered response")
#     for index in resp["indices"]:
#         assert_http_error(index["table_name"] == "chunks", "Filter not applied correctly")

#     print("List indices with filters test passed")
#     print("~" * 100)


def test_delete_index():
    print("Testing: Delete index")
    # First create an index to delete
    index_name = "test_delete_index_" + str(uuid.uuid4())[:8]

    config = {
        "table_name": "chunks",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {"m": 16, "ef_construction": 64, "ef": 40},
        "index_name": index_name,
        "index_column": "vec",
        "concurrently": True,
    }

    # Create the index
    client.indices.create(config=config, run_with_orchestration=True)[
        "results"
    ]

    # Delete the index
    delete_resp = client.indices.delete(
        index_name=index_name, table_name="chunks"
    )["results"]

    assert_http_error(
        "message" in delete_resp, "No message in delete response"
    )

    # Verify deletion by trying to get the index
    try:
        client.indices.retrieve(index_name=index_name, table_name="chunks")
        print("Expected error for deleted index, got none")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            "not found" in str(e).lower(), "Unexpected error message"
        )

    print("Delete index test passed")
    print("~" * 100)


def test_error_handling():
    print("Testing: Error handling")
    try:
        # Try to get a non-existent index
        client.indices.retrieve(
            index_name="nonexistent_index", table_name="chunks"
        )
        print("Expected error for non-existent index, got none")
        sys.exit(1)
    except R2RException as e:
        assert_http_error(
            "not found" in str(e).lower(), "Unexpected error message"
        )
    print("Error handling test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R SDK Indices Integration Tests"
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
