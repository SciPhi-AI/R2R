import json
import sys

from r2r import R2RClient

client = R2RClient()


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


def test_ingest_sample_file_sdk():
    print("Testing: Ingest sample file SDK")
    file_paths = ["core/examples/data/uber_2021.pdf"]
    ingest_response = client.ingest_files(file_paths=file_paths)

    if not ingest_response["results"]:
        print("Ingestion test failed")
        sys.exit(1)

    print("Ingestion successful")
    print("~" * 100)


def test_reingest_sample_file_sdk():
    print("Testing: Ingest sample file SDK")
    file_paths = ["core/examples/data/uber_2021.pdf"]
    try:
        reingest_response = client.ingest_files(file_paths=file_paths)
        print(
            "Re-ingestion test failed: Expected an error but ingestion succeeded"
        )
        sys.exit(1)
    except Exception as e:
        error_message = str(e)
        if (
            "Must increment version number before attempting to overwrite document"
            not in error_message
        ):
            print(
                f"Re-ingestion test failed: Unexpected error - {error_message}"
            )
            sys.exit(1)
        else:
            print("Re-ingestion failed as expected")

    print("Re-ingestion test passed")
    print("~" * 100)


def test_document_overview_sample_file_sdk():
    print("Testing: Document overview contains 'uber.txt'")
    documents_overview = client.documents_overview()

    aristotle_document = {
        "title": "aristotle.txt",
        "type": "txt",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "version": "v0",
        "metadata": {"title": "aristotle.txt", "version": "v0"},
    }

    if not any(
        all(doc.get(k) == v for k, v in aristotle_document.items())
        for doc in documents_overview
    ):
        print("Document overview test failed")
        print("Aristotle document not found in the overview")
        sys.exit(1)
    print("Document overview test passed")
    print("~" * 100)


def test_vector_search_sample_file_filter_sdk():
    print("Testing: Vector search")
    results = client.search(
        query="Who was aristotle?",
        filters={
            "document_id": {"$eq": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1"}
        },
    )

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "text": "Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.",
        "extraction_id": "ff8accdb-791e-5b6d-a83a-5adc32c4222c",
        "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": lambda x: 0.77 <= x <= 0.79,
    }
    compare_result_fields(lead_result, expected_lead_search_result)

    print("Vector search test passed")
    print("~" * 100)


def test_hybrid_search_sample_file_filter_sdk():
    print("Testing: Hybrid search")
    results = client.search(
        query="Who was aristotle?",
        vector_search_settings={"use_hybrid_search": True},
        filters={
            "document_id": {"$eq": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1"}
        },
    )

    if not results:
        print("Hybrid search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "text": "Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.",
        "extraction_id": "ff8accdb-791e-5b6d-a83a-5adc32c4222c",
        "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": lambda x: 0.77 <= x <= 0.79,
    }
    compare_result_fields(lead_result, expected_lead_search_result)

    print("Hybrid search test passed")
    print("~" * 100)


def test_rag_response_sample_file_sdk():
    print("Testing: RAG query for Aristotle's birth year")
    response = client.rag(query="What year was Aristotle born?")

    expected_answer = "Aristotle was born in 384 BC"

    if expected_answer not in response:
        print(
            f"RAG query test failed: Expected answer '{expected_answer}' not found in '{response}'"
        )
        sys.exit(1)

    print("RAG response test passed")
    print("~" * 100)


def test_rag_response_stream_sample_file_sdk():
    print("Testing: Streaming RAG query for who Aristotle was")

    rag_agent_response = client.agent(
        messages=[{"role": "user", "content": "who was aristotle"}],
        vector_search_settings={"use_hybrid_search": True},
        rag_generation_config={"stream": True},
    )

    output = ""
    for response in rag_agent_response:
        output += response

    if "<search>" not in output or "</search>" not in output:
        print(
            "Streaming RAG query test failed: Search results not found in output"
        )
        sys.exit(1)

    if "<completion>" not in output or "</completion>" not in output:
        print(
            "Streaming RAG query test failed: Completion not found in output"
        )
        sys.exit(1)

    print("RAG response stream test passed")
    print("~" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please specify a test function to run")
        sys.exit(1)

    test_function = sys.argv[1]
    globals()[test_function]()
