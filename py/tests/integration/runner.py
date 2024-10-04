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


def test_ingest_sample_file_cli():
    print("Testing: Ingest sample file CLI")
    run_command("poetry run r2r ingest-sample-file")
    print("Ingestion successful")


def test_document_overview_sample_file_cli():
    print("Testing: Document overview contains 'aristotle.txt'")
    output = run_command("poetry run r2r documents-overview")
    output = output.replace("'", '"')
    output_lines = output.strip().split('\n')[1:]
    documents = [json.loads(ele) for ele in output_lines]

    aristotle_document = {
        "title": "aristotle.txt",
        "type": "txt",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "version": "v0",
        "metadata": {"title": "aristotle.txt", "version": "v0"},
    }

    # Check if any document in the overview matches the Aristotle document
    if not any(
        all(doc.get(k) == v for k, v in aristotle_document.items())
        for doc in documents
    ):
        print("Document overview test failed")
        print("Aristotle document not found in the overview")
        sys.exit(1)
    print("Document overview test passed")

def test_vector_search_sample_file_filter_cli():
    print("Testing: Vector search")
    output = run_command(
        """poetry run r2r search --query="Who was aristotle?" """
    )
    # Split the output into lines and remove the first and last lines
    output_lines = output.strip().split('\n')[1:-1]
    # Replace single quotes with double quotes in each line
    cleaned_output_lines = [line.replace("'", '"') for line in output_lines]
    results = []
    for line in cleaned_output_lines:
        try:
            result = json.loads(line)
            results.append(result)
        # Skip lines that are not valid JSON b/c of the single quote replacement
        except json.JSONDecodeError:
            continue

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    expected_lead_search_result = {
        "extraction_id": "ff8accdb-791e-5b6d-a83a-5adc32c4222c",
        "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1", 
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": 0.7820796370506287,
        "text": """Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science."""
    }
    lead_result = results[0]

    if lead_result['text'] != expected_lead_search_result['text']:
        print('Vector search test failed: Incorrect search result text')
        print('Expected lead search text:', expected_lead_search_result['text'])
        print('Actual lead search text:', lead_result['text'])
        sys.exit(1)

    if lead_result['extraction_id'] != expected_lead_search_result['extraction_id']:
        print("Vector search test failed: Incorrect extraction_id")
        print('Expected extraction_id:', expected_lead_search_result['extraction_id'])
        print('Actual extraction_id:', lead_result['extraction_id'])
        sys.exit(1)

    if lead_result['document_id'] != expected_lead_search_result['document_id']:
        print("Vector search test failed: Incorrect document_id")
        print('Expected document_id:', expected_lead_search_result['document_id'])
        print('Actual document_id:', lead_result['document_id'])
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
