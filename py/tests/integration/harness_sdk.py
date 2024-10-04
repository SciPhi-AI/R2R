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
    documents_overview = client.documents_overview()["results"]

    uber_document = {
        "id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
        "title": "uber_2021.pdf",
        "type": "pdf",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
        # "version": "v0",
        # "metadata": {"title": "uber_2021.pdf"},
    }

    if not any(
        all(doc.get(k) == v for k, v in uber_document.items())
        for doc in documents_overview
    ):
        print("Document overview test failed")
        print("Uber document not found in the overview")
        sys.exit(1)
    print("Document overview test passed")
    print("~" * 100)


def test_document_chunks_sample_file_sdk():
    print("Testing: Document chunks")
    document_id = "3e157b3a-8469-51db-90d9-52e7d896b49b"  # Replace with the actual document ID
    chunks = client.document_chunks(document_id=document_id)["results"]

    lead_chunk = {
        "extraction_id": "57d761ac-b2df-529c-9c47-6e6e1bbf854f",
        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
        "text": "UNITED STATESSECURITIES AND EXCHANGE COMMISSION\nWashington, D.C. 20549\n____________________________________________ \nFORM\n 10-K____________________________________________ \n(Mark One)\n\n ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934For the fiscal year ended\n December 31, 2021OR",
        "metadata": {
            "version": "v0",
            "chunk_order": 0,
            "document_type": "pdf",
        },
    }

    assert len(chunks) >= 100 and lead_chunk == chunks[0]
    print("Document chunks test passed")
    print("~" * 100)


def test_vector_search_sample_file_filter_sdk():
    print("Testing: Vector search")
    results = client.search(
        query="What was Uber's recent profit??",
        vector_search_settings={
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            }
        },
    )["results"]["vector_search_results"]

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "text": "was $17.5 billion, or up 57% year-over-year, reflecting the overall growth in our Delivery business and an increase in Freight revenue attributable tothe\n acquisition of Transplace in the fourth quarter of 2021 as well as growth in the number of shippers and carriers on the network combined with an increase involumes with our top shippers.\nNet\n loss attributable to Uber Technologies, Inc. was $496 million, a 93% improvement year-over-year, driven by a $1.6 billion pre-tax gain on the sale of ourATG\n Business to Aurora, a $1.6 billion pre-tax  net benefit relating to Ubers equity investments, as  well as reductions in our fixed cost structure and increasedvariable cost effi\nciencies. Net loss attributable to Uber Technologies, Inc. also included $1.2 billion of stock-based compensation expense.Adjusted\n EBITDA loss was $774 million, improving $1.8 billion from 2020 with Mobility Adjusted EBITDA profit of $1.6 billion. Additionally, DeliveryAdjusted",
        "extraction_id": "6b4cdb93-f6f5-5ff4-8a89-7a4b1b7cd034",
        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": lambda x: 0.71 <= x <= 0.73,
    }
    compare_result_fields(lead_result, expected_lead_search_result)

    print("Vector search test passed")
    print("~" * 100)


def test_hybrid_search_sample_file_filter_sdk():
    print("Testing: Hybrid search")

    results = client.search(
        query="What was Uber's recent profit??",
        vector_search_settings={
            "use_hybrid_search": True,
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            },
        },
    )["results"]["vector_search_results"]

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "text": "was $17.5 billion, or up 57% year-over-year, reflecting the overall growth in our Delivery business and an increase in Freight revenue attributable tothe\n acquisition of Transplace in the fourth quarter of 2021 as well as growth in the number of shippers and carriers on the network combined with an increase involumes with our top shippers.\nNet\n loss attributable to Uber Technologies, Inc. was $496 million, a 93% improvement year-over-year, driven by a $1.6 billion pre-tax gain on the sale of ourATG\n Business to Aurora, a $1.6 billion pre-tax  net benefit relating to Ubers equity investments, as  well as reductions in our fixed cost structure and increasedvariable cost effi\nciencies. Net loss attributable to Uber Technologies, Inc. also included $1.2 billion of stock-based compensation expense.Adjusted\n EBITDA loss was $774 million, improving $1.8 billion from 2020 with Mobility Adjusted EBITDA profit of $1.6 billion. Additionally, DeliveryAdjusted",
        "extraction_id": "6b4cdb93-f6f5-5ff4-8a89-7a4b1b7cd034",
        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": lambda x: 0.016 <= x <= 0.018,
        "metadata": {
            "version": "v0",
            "chunk_order": 587,
            "document_type": "pdf",
            "semantic_rank": 1,
            "full_text_rank": 200,
            "associated_query": "What was Uber's recent profit??",
        },
    }
    compare_result_fields(lead_result, expected_lead_search_result)

    print("Hybrid search test passed")
    print("~" * 100)


def test_rag_response_sample_file_sdk():
    print("Testing: RAG query for Uber's recent P&L")
    response = client.rag(
        query="What was Uber's recent profit and loss?",
        vector_search_settings={
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            }
        },
    )["results"]["completion"]["choices"][0]["message"]["content"]

    expected_answer_0 = "net loss"
    expected_answer_1 = "$496 million"

    if expected_answer_0 not in response or expected_answer_1 not in response:
        print(
            f"RAG query test failed: Expected answer(s) '{expected_answer_0}, {expected_answer_1}' not found in '{response}'"
        )
        sys.exit(1)

    print("RAG response test passed")
    print("~" * 100)


def test_rag_response_stream_sample_file_sdk():
    print("Testing: Streaming RAG query for Uber's recent P&L")
    response = client.rag(
        query="What was Uber's recent profit and loss?",
        rag_generation_config={"stream": True},
        vector_search_settings={
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            }
        },
    )  # ["results"]["completion"]["choices"][0]["message"]["content"]

    response = ""
    for res in response:
        response += res
        print(res)

    expected_answer_0 = "net loss"
    expected_answer_1 = "$496 million"

    if expected_answer_0 not in response or expected_answer_1 not in response:
        print(
            f"RAG query test failed: Expected answer(s) '{expected_answer_0}, {expected_answer_1}' not found in '{response}'"
        )
        sys.exit(1)

    print("Streaming RAG response test passed")
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


def test_agent_sample_file_sdk():
    print("Testing: Agent query for Uber's recent P&L")
    response = client.agent(
        messages=[
            {
                "role": "user",
                "content": "What was Uber's recent profit and loss?",
            }
        ],
        rag_generation_config={"stream": False},
        vector_search_settings={
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            }
        },
    )["results"]
    response_content = response["messages"][-1]["content"]

    expected_answer_0 = "net loss"
    expected_answer_1 = "$496 million"

    if (
        expected_answer_0 not in response_content
        or expected_answer_1 not in response_content
    ):
        print(
            f"Agent query test failed: Expected answer(s) '{expected_answer_0}, {expected_answer_1}' not found in '{response_content}'"
        )
        sys.exit(1)

    print("Agent response test passed")
    print("~" * 100)


def test_agent_stream_sample_file_sdk():
    print("Testing: Streaming agent query for who Aristotle was")

    response = client.agent(
        messages=[
            {
                "role": "user",
                "content": "What was Uber's recent profit and loss?",
            }
        ],
        rag_generation_config={"stream": True},
        vector_search_settings={
            "search_filters": {
                "document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}
            }
        },
    )
    output = ""
    for response in response:
        output += response["content"]

    expected_answer_0 = "net loss"
    expected_answer_1 = "$496 million"

    if expected_answer_0 not in response or expected_answer_1 not in response:
        print(
            f"Agent query test failed: Expected answer(s) '{expected_answer_0}, {expected_answer_1}' not found in '{response_content}'"
        )
        sys.exit(1)

    print("Agent response stream test passed")
    print("~" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please specify a test function to run")
        sys.exit(1)

    test_function = sys.argv[1]
    globals()[test_function]()
