import argparse
import sys
import time

from r2r import Message, R2RClient, R2RException


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


def test_ingested_zerox_document():
    print("Testing: Ingest sample file SDK")
    documents_overview = client.documents_overview()
    results = documents_overview["results"]
    assert results[0]["id"] == "7b0f40c5-2ace-5781-ae35-ead99ddee8c5"
    assert len(results) == 1
    assert results[0]["ingestion_status"] == "success"


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
