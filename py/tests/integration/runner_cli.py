import json
import subprocess
import sys
import time

import requests


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
    time.sleep(30)
    print("Ingestion successful")
    print("~" * 100)


def test_ingest_sample_file_2_cli():
    """
    Ingesting Aristotle v2, the smaller version of the file.
    """
    print("Testing: Ingest sample file CLI 2")
    run_command("poetry run r2r ingest-sample-file --v2")
    time.sleep(30)
    print("Ingestion successful")
    print("~" * 100)


def compare_document_fields(documents, expected_doc):
    for doc in documents:
        mismatched_fields = {}
        for key, expected_value in expected_doc.items():
            actual_value = doc.get(key)
            if actual_value != expected_value:
                mismatched_fields[key] = {
                    "expected": expected_value,
                    "actual": actual_value,
                }

        if not mismatched_fields:  # If all fields match
            return True

        # Print mismatches for debugging
        print(f"\nMismatched fields in document: {doc['title']}")
        for field, values in mismatched_fields.items():
            print(f"Field '{field}':")
            print(f"  Expected: {values['expected']}")
            print(f"  Actual:   {values['actual']}")
        print()

    return False


def test_document_overview_sample_file_cli():
    print("Testing: Document overview contains 'aristotle.txt'")
    output = run_command("poetry run r2r documents-overview")

    # Skip non-JSON lines and find the JSON content
    output_lines = output.strip().split("\n")
    json_lines = [
        line for line in output_lines if line.strip().startswith("{")
    ]

    documents = []
    for line in json_lines:
        try:
            # Replace Python None with JSON null and single quotes with double quotes
            json_str = line.replace("'", '"').replace(": None", ": null")
            doc = json.loads(json_str)
            documents.append(doc)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Problem line: {line}")
            continue

    aristotle_document = {
        "title": "aristotle.txt",
        "document_type": "txt",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "version": "v0",
        "metadata": {"title": "aristotle.txt", "version": "v0"},
    }

    if not compare_document_fields(documents, aristotle_document):
        print("Document overview test failed")
        print("Aristotle document not found in the overview")
        print("All documents:", documents)
        sys.exit(1)

    print("Document overview test passed")
    print("~" * 100)


def test_document_chunks_sample_file_cli():
    print("Testing: Document chunks")
    output = run_command(
        "poetry run r2r document-chunks --document-id=9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
    )
    output = output.replace("'", '"')
    output_lines = output.strip().split("\n")[1:]
    aristotle_is_in_chunks = False
    for line in output_lines:
        if "aristotle" in line.lower():
            aristotle_is_in_chunks = True
            break
    assert len(output_lines) >= 100 and aristotle_is_in_chunks
    print("Document chunks test passed")
    print("~" * 100)


def test_delete_and_reingest_sample_file_cli():
    print("Testing: Delete and re-ingest Aristotle document")

    # Delete the Aristotle document
    delete_output = run_command(
        "poetry run r2r delete --filter='document_id:eq:9fbe403b-c11c-5aae-8ade-ef22980c3ad1'"
    )

    # Check if the deletion was successful
    if "'results': {}" not in delete_output:
        print("Delete and re-ingest test failed: Deletion unsuccessful")
        print("Delete output:", delete_output)
        sys.exit(1)

    print("Aristotle document deleted successfully")

    # Re-ingest the sample file
    run_command("poetry run r2r ingest-sample-file")
    print("Sample file re-ingested successfully")

    print("Delete and re-ingest test passed")
    print("~" * 100)


def test_update_file_cli():
    print("Testing: Update document")
    update_file_output = run_command(
        "r2r update-files core/examples/data/aristotle_v2.txt --document-ids=9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
    )
    print("Sample file updatesuccessfully")

    print("Update test passed")
    print("~" * 100)


def test_vector_search_sample_file_filter_cli():
    print("Testing: Vector search")
    output = run_command(
        """poetry run r2r search --query="Who was aristotle?" --filters='{"document_id": {"$eq": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1"}}'"""
    )

    expected_lead_search_result = {
        "text": "Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.",
        "chunk_id": "ff8accdb-791e-5b6d-a83a-5adc32c4222c",
        "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        # "score": lambda x: 0.77 <= x <= 0.79,
    }
    # compare_result_fields(output, expected_lead_search_result)
    for value in expected_lead_search_result.values():
        assert value in output

    print("Vector search test passed")
    print("~" * 100)


def test_hybrid_search_sample_file_filter_cli():
    print("Testing: Vector search")
    output = run_command(
        """poetry run r2r search --query="Who was aristotle?" --use-hybrid-search --filters='{"document_id": {"$eq": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1"}}'"""
    )
    output_lines = output.strip().split("\n")[1:-1]
    cleaned_output_lines = [line.replace("'", '"') for line in output_lines]
    results = []
    for line in cleaned_output_lines:
        try:
            result = json.loads(line)
            results.append(result)
        except json.JSONDecodeError:
            continue

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    # TODO - Fix loading of CLI result to allow comparison below
    # (e.g. lead result does not properly load as a dictionary)
    # lead_result = results[0]
    # expected_lead_search_result = {
    #     "text": "Life\nIn general, the details of Aristotle's life are not well-established. The biographies written in ancient times are often speculative and historians only agree on a few salient points.[B]\n\nAristotle was born in 384 BC[C] in Stagira, Chalcidice,[2] about 55 km (34 miles) east of modern-day Thessaloniki.[3][4] His father, Nicomachus, was the personal physician to King Amyntas of Macedon. While he was young, Aristotle learned about biology and medical information, which was taught by his father.[5] Both of Aristotle's parents died when he was about thirteen, and Proxenus of Atarneus became his guardian.[6] Although little information about Aristotle's childhood has survived, he probably spent some time within the Macedonian palace, making his first connections with the Macedonian monarchy.[7]",
    #     "chunk_id": "f6f5cfb6-8654-5e1c-b574-849a8a313452",
    #     "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
    #     "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
    #     "score": lambda x: 0.016 <= x <= 0.018,
    #     "full_text_rank": 10,
    #     "semantic_rank": 5,
    # }
    # compare_result_fields(lead_result, expected_lead_search_result)

    print("Vector search test passed")
    print("~" * 100)


def test_rag_response_sample_file_cli():
    print("Testing: RAG query for Aristotle's birth year")
    output = run_command(
        "poetry run r2r rag --query='What year was Aristotle born?'"
    )
    # TODO - Can we fix the test to check by loading JSON output?
    # response = json.loads(output)

    expected_answer = "Aristotle was born in 384 BC"

    if expected_answer not in output:
        print(
            f"RAG query test failed: Expected answer '{expected_answer}' not found in '{output}'"
        )
        sys.exit(1)

    print("RAG response test passed")
    print("~" * 100)


def test_rag_response_stream_sample_file_cli():
    print("Testing: Streaming RAG query for who Aristotle was")

    # Run the command and capture the output
    # output = run_command("poetry run r2r rag --query='who was aristotle' --use-hybrid-search --stream", capture_output=True)
    process = subprocess.Popen(
        [
            "poetry",
            "run",
            "r2r",
            "rag",
            "--query='who was aristotle'",
            "--use-hybrid-search",
            "--stream",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output, _ = process.communicate()

    # Check if the output contains the search and completion tags
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


def test_kg_create_graph_sample_file_cli():
    print("Testing: KG create graph")
    print("Calling `poetry run r2r create-graph --run`")
    output = run_command("poetry run r2r create-graph --run")

    time.sleep(60)

    response = requests.get(
        "http://localhost:7272/v2/entities/",
        params={
            "collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
            "limit": 1000,
            "entity_level": "document",
        },
    )

    if response.status_code != 200:
        print("KG create graph test failed: Graph not created")
        sys.exit(1)

    entities_list = [
        ele["name"] for ele in response.json()["results"]["entities"]
    ]

    print(entities_list)

    documents_overview = run_command("poetry run r2r documents-overview")
    print(documents_overview)
    assert len(entities_list) >= 1
    assert "ARISTOTLE" in entities_list

    print("KG create graph test passed")
    print("~" * 100)


def test_kg_deduplicate_entities_sample_file_cli():
    print("Testing: KG deduplicate entities")
    output = run_command("poetry run r2r deduplicate-entities --run")

    print(output)

    if "queued" in output:
        time.sleep(45)

    response = requests.get(
        "http://localhost:7272/v2/entities",
        params={
            "collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
            "entity_level": "collection",
        },
    )

    if response.status_code != 200:
        print("KG deduplicate entities test failed: Communities not created")
        sys.exit(1)

    entities = response.json()["results"]["entities"]
    assert len(entities) >= 1

    entities_list = [ele["name"] for ele in entities]
    assert "ARISTOTLE" in entities_list

    print("KG deduplicate entities test passed")
    print("~" * 100)


def test_kg_enrich_graph_sample_file_cli():
    print("Testing: KG enrich graph")
    output = run_command("poetry run r2r enrich-graph --run")

    if "queued" in output:
        time.sleep(60)

    response = requests.get(
        "http://localhost:7272/v2/communities",
        params={"collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"},
    )

    if response.status_code != 200:
        print("KG enrichment test failed: Communities not created")
        sys.exit(1)

    communities = response.json()["results"]["communities"]
    assert len(communities) >= 1

    for community in communities:
        assert "community_number" in community
        assert "level" in community
        assert "collection_id" in community
        assert "name" in community
        assert "summary" in community
        assert "findings" in community

    print("KG enrichment test passed")
    print("~" * 100)


def test_kg_search_sample_file_cli():
    print("Testing: KG search")

    output = run_command(
        "poetry run r2r search --query='Who was aristotle?' --use-kg-search"
    )

    output_lines = output.strip().split("\n")
    results = []
    for line in output_lines:
        line = line.strip()

        try:
            result = json.loads(line)
            results.append(result)
        except json.JSONDecodeError as e:
            results.append(line)
            continue

    if not results:
        print("KG search test failed: No results returned")
        sys.exit(1)

    # there should be vector search and KG search results
    kg_search_result_present = False
    entities_found = False
    communities_found = False
    for result in results:
        if "{'method': 'local'" in result:
            kg_search_result_present = True
        if "entity" in result:
            entities_found = True
        if "community" in result:
            communities_found = True

    assert kg_search_result_present, "No KG search result present"
    assert entities_found, "No entities found"
    assert communities_found, "No communities found"

    print("KG search test passed")
    print("~" * 100)


def test_kg_delete_graph_sample_file_cli():
    print("Testing: KG delete graph")
    output = run_command(
        "poetry run r2r delete-graph-for-collection --collection-id=122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )
    print(output)

    response = requests.get(
        "http://localhost:7272/v2/communities",
        params={"collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"},
    )

    assert response.json()["results"]["communities"] == []

    response = requests.get(
        "http://localhost:7272/v2/entities",
        params={"collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"},
    )

    assert response.json()["results"]["entities"] != []

    print("KG delete graph test passed")
    print("~" * 100)


def test_kg_delete_graph_with_cascading_sample_file_cli():
    print("Testing: KG delete graph with cascading")
    output = run_command(
        "poetry run r2r delete-graph-for-collection --collection-id=122fdf6a-e116-546b-a8f6-e4cb2e2c0a09 --cascade"
    )
    print(output)

    response = requests.get(
        "http://localhost:7272/v2/entities",
        params={"collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"},
    )

    assert response.json()["results"]["entities"] == []

    response = requests.get(
        "http://localhost:7272/v2/triples",
        params={"collection_id": "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"},
    )

    assert response.json()["results"]["triples"] == []

    print("KG delete graph with cascading test passed")
    print("~" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please specify a test function to run")
        sys.exit(1)

    test_function = sys.argv[1]
    globals()[test_function]()
