# File: tests/integration/r2r_integration_tests.py

import json
import subprocess
import sys


def run_command(command):
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Command failed: {command}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout


def test_ingest_sample_files_cli():
    print("Testing: Ingest sample files")
    run_command("poetry run r2r ingest-sample-files")
    print("Ingestion successful")


def test_document_ingestion_cli():
    print("Testing: Document ingestion")
    output = run_command("poetry run r2r documents-overview")
    documents = json.loads(output)

    expected_document = {
        "id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
        "title": "aristotle.txt",
        "type": "txt",
        "ingestion_status": "success",
        "kg_extraction_status": "success",
        "version": "v0",
        "metadata": {"title": "aristotle.txt", "version": "v0"},
    }

    if not any(
        all(doc.get(k) == v for k, v in expected_document.items())
        for doc in documents
    ):
        print("Document ingestion test failed")
        print(f"Expected document not found in output: {output}")
        sys.exit(1)
    print("Document ingestion test passed")


def test_vector_search_cli():
    print("Testing: Vector search")
    output = run_command(
        "poetry run r2r search --query='What was Uber's profit in 2020?'"
    )
    results = json.loads(output)
    if not results.get("results"):
        print("Vector search test failed: No results returned")
        sys.exit(1)
    print("Vector search test passed")


def test_rag_query_cli():
    print("Testing: RAG query")
    output = run_command("poetry run r2r rag --query='Who was Aristotle?'")
    response = json.loads(output)
    if not response.get("answer"):
        print("RAG query test failed: No answer returned")
        sys.exit(1)
    print("RAG query test passed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please specify a test function to run")
        sys.exit(1)

    test_function = sys.argv[1]
    globals()[test_function]()
