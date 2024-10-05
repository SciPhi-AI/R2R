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


def test_ingest_sample_file_with_config_sdk():
    print("Testing: Ingest sample file 2")
    file_paths = ["core/examples/data/aristotle_v2.txt"]

    ingest_response = client.ingest_files(
        file_paths=file_paths, ingestion_config={"chunk_size": 4_096}
    )

    if not ingest_response["results"]:
        print("Ingestion test failed")
        sys.exit(1)

    document_id = ingest_response["results"][0]["document_id"]

    if document_id != "c3291abf-8a4e-5d9d-80fd-232ef6fd8526":
        print("Ingestion test failed: Incorrect document ID")
        sys.exit(1)

    if len(ingest_response["results"]) != 1:
        print("Ingestion test failed: Incorrect number of results")
        sys.exit(1)

    print("Ingestion with config successful")
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


def test_delete_and_reingest_sample_file_sdk():
    print("Testing: Delete and re-ingest the Uber document")

    # Delete the Aristotle document
    delete_response = client.delete(
        {"document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}}
    )

    # Check if the deletion was successful
    if delete_response["results"] != {}:
        print("Delete and re-ingest test failed: Deletion unsuccessful")
        print("Delete response:", delete_response)
        sys.exit(1)

    print("Uber document deleted successfully")

    # Re-ingest the sample file
    file_paths = ["core/examples/data/uber_2021.pdf"]
    ingest_response = client.ingest_files(file_paths=file_paths)

    if not ingest_response["results"]:
        print("Delete and re-ingest test failed: Re-ingestion unsuccessful")
        sys.exit(1)

    print("Sample file re-ingested successfully")

    print("Delete and re-ingest test passed")
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
    )

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


def test_user_registration_and_login():
    print("Testing: User registration and login")

    # Register a new user
    user_result = client.register("user_test@example.com", "password123")[
        "results"
    ]

    # Login immediately (assuming email verification is disabled)
    login_results = client.login("user_test@example.com", "password123")[
        "results"
    ]

    if "access_token" not in login_results:
        print("User registration and login test failed")
        sys.exit(1)

    if "refresh_token" not in login_results:
        print("User registration and login test failed")
        sys.exit(1)

    print("User registration and login test passed")
    print("~" * 100)


def test_duplicate_user_registration():
    print("Testing: Duplicate user registration")

    # Register a new user
    client.register("duplicate_test@example.com", "password123")["results"]

    # Attempt to register the same user again
    try:
        client.register("duplicate_test@example.com", "password123")
        print(
            "Duplicate user registration test failed: Expected an error but registration succeeded"
        )
        sys.exit(1)
    except Exception as e:
        error_message = str(e)
        if "User with this email already exists" not in error_message:
            print(
                f"Duplicate user registration test failed: Unexpected error - {error_message}"
            )
            sys.exit(1)
        else:
            print("Duplicate user registration failed as expected")

    print("Duplicate user registration test passed")
    print("~" * 100)


def test_token_refresh():
    print("Testing: Access token refresh")
    client.login("user_test@example.com", "password123")

    refresh_result = client.refresh_access_token()["results"]
    if "access_token" not in refresh_result:
        print("Access token refresh test failed")
        sys.exit(1)

    if "refresh_token" not in refresh_result:
        print("Access token refresh test failed")
        sys.exit(1)

    print("Access token refresh test passed")
    print("~" * 100)


def test_user_document_management():
    print("Testing: User document management")
    client.login("user_test@example.com", "password123")

    # Ingest a sample file for the logged-in user
    ingestion_result = client.ingest_files(
        ["core/examples/data/lyft_2021.pdf"]
    )["results"]

    # Check the ingestion result
    if not ingestion_result:
        print("User document management test failed: Ingestion failed")
        sys.exit(1)

    ingested_document = ingestion_result[0]
    expected_ingestion_result = {
        "message": "Ingestion task completed successfully.",
        "task_id": None,
        "document_id": lambda x: len(x)
        == 36,  # Check if document_id is a valid UUID
    }
    compare_result_fields(ingested_document, expected_ingestion_result)

    # Check the user's documents
    documents_overview = client.documents_overview()["results"]

    if not documents_overview:
        print(
            "User document management test failed: No documents found in the overview"
        )
        sys.exit(1)

    ingested_document_overview = documents_overview[0]
    expected_document_overview = {
        "id": ingested_document["document_id"],
        "title": "lyft_2021.pdf",
        "user_id": lambda x: len(x) == 36,  # Check if user_id is a valid UUID
        "type": "pdf",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "version": "v0",
        "collection_ids": lambda x: len(x) == 1
        and len(x[0]) == 36,  # Check if collection_ids contains a valid UUID
        "metadata": {"version": "v0"},
    }
    compare_result_fields(
        ingested_document_overview, expected_document_overview
    )

    print("User document management test passed")
    print("~" * 100)


def test_user_search_and_rag():
    print("Testing: User search and RAG")
    client.login("user_test@example.com", "password123")

    # Perform a search
    search_query = "What was Lyft's revenue in 2021?"
    search_result = client.search(query=search_query)["results"]
    print(f"Search Result:\n{search_result}")

    # Check the search result
    if not search_result["vector_search_results"]:
        print("User search test failed: No search results found")
        sys.exit(1)

    lead_search_result = search_result["vector_search_results"][0]
    expected_search_result = {
        "text": lambda x: "Lyft" in x and "revenue" in x and "2021" in x,
        "score": lambda x: 0.5 <= x <= 1.0,
    }
    compare_result_fields(lead_search_result, expected_search_result)

    # Perform a RAG query
    rag_query = "What was Lyft's total revenue in 2021 and how did it compare to the previous year?"
    rag_result = client.rag(query=rag_query)["results"]

    # Check the RAG result
    if not rag_result["completion"]["choices"]:
        print("User RAG test failed: No RAG results found")
        sys.exit(1)

    rag_response = rag_result["completion"]["choices"][0]["message"]["content"]
    expected_rag_response = (
        lambda x: "Lyft" in x
        and "revenue" in x
        and "2021" in x
        and "2020" in x
    )

    if not expected_rag_response(rag_response):
        print(
            f"User RAG test failed: Unexpected RAG response - {rag_response}"
        )
        sys.exit(1)

    print("User search and RAG test passed")
    print("~" * 100)


def test_user_password_management():
    print("Testing: User password management")

    # Test for duplicate user
    client.login("duplicate_test@example.com", "password123")

    # Change password
    client.change_password("password123", "new_password")
    # Request password reset
    client.request_password_reset("user_test@example.com")

    # Confirm password reset (after user receives reset token)
    # reset_confirm_result = client.confirm_password_reset("reset_token_here", "password123")
    # print(f"Reset Confirm Result:\n{reset_confirm_result}")

    print("User password management test passed")
    print("~" * 100)


def test_user_profile_management():
    print("Testing: User profile management")

    client.register("test_user_123456@example.com", "password123")
    client.login("test_user_123456@example.com", "password123")

    # Get user profile
    profile = client.user()["results"]
    print(f"User Profile:\n{profile}")

    # Update user profile
    update_result = client.update_user(
        user_id=str(profile["id"]), name="John Doe", bio="R2R enthusiast"
    )
    print(f"Update User Result:\n{update_result}")

    print("User profile management test passed")
    print("~" * 100)


def test_user_logout():
    print("Testing: User logout")

    logout_result = client.logout()
    print(f"Logout Result:\n{logout_result}")

    print("User logout test passed")
    print("~" * 100)


def test_superuser_capabilities():
    print("Testing: Superuser capabilities")

    # Login as admin
    login_result = client.login("admin@example.com", "change_me_immediately")
    print(f"Admin Login Result:\n{login_result}")

    # Access users overview
    users_overview = client.users_overview()
    print(f"Users Overview:\n{users_overview}")

    # Access system-wide logs
    logs = client.logs()
    print(f"System Logs:\n{logs}")

    # Perform analytics
    analytics_result = client.analytics(
        {"search_latencies": "search_latency"},
        {"search_latencies": ["basic_statistics", "search_latency"]},
    )
    print(f"Analytics Result:\n{analytics_result}")

    print("Superuser capabilities test passed")
    print("~" * 100)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please specify a test function to run")
        sys.exit(1)

    test_function = sys.argv[1]
    globals()[test_function]()
