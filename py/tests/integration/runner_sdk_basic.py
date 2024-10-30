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


def test_ingest_sample_file_sdk():
    print("Testing: Ingest sample file SDK")
    file_paths = ["core/examples/data/aristotle.txt"]
    ingest_response = client.ingest_files(
        file_paths=file_paths, run_with_orchestration=False
    )

    if not ingest_response["results"]:
        print("Ingestion test failed")
        sys.exit(1)
    print("Ingestion successful")
    print("~" * 100)


def test_ingest_sample_file_2_sdk():
    print("Testing: Ingest sample file SDK 2")
    file_paths = [f"core/examples/data_dedup/a{i}.txt" for i in range(1, 11)]
    ingest_response = client.ingest_files(
        file_paths=file_paths, run_with_orchestration=False
    )

    if not ingest_response["results"]:
        print("Ingestion test failed")
        sys.exit(1)

    print("Ingestion successful")
    print("~" * 100)


def test_ingest_sample_file_3_sdk():
    print("Testing: Ingest sample file SDK 2")
    file_paths = ["core/examples/data/aristotle_v2.txt"]
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
        file_paths=file_paths,
        ingestion_config={"chunk_size": 4_096},
        run_with_orchestration=False,
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


def test_remove_all_files_and_ingest_sample_file_sdk():
    document_ids = [
        doc["id"] for doc in client.documents_overview()["results"]
    ]
    for document_id in document_ids:
        client.delete({"document_id": {"$eq": document_id}})

    client.ingest_files(file_paths=["core/examples/data/aristotle_v2.txt"])


def test_reingest_sample_file_sdk():
    print("Testing: Ingest sample file SDK")
    file_paths = ["core/examples/data/aristotle.txt"]
    try:
        results = client.ingest_files(
            file_paths=file_paths, run_with_orchestration=False
        )

        if "task_id" not in results["results"][0]:
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

    sample_document = {
        "id": "db02076e-989a-59cd-98d5-e24e15a0bd27",
        "title": "aristotle.txt",
        "document_type": "txt",
        "ingestion_status": "success",
        "kg_extraction_status": "pending",
        "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
        # "version": "v0",
        # "metadata": {"title": "uber_2021.pdf"},
    }

    if not any(
        all(doc.get(k) == v for k, v in sample_document.items())
        for doc in documents_overview
    ):
        print("Document overview test failed")
        print("sample document not found in the overview")
        sys.exit(1)
    print("Document overview test passed")
    print("~" * 100)


def test_document_chunks_sample_file_sdk():
    print("Testing: Get document chunks from sample file")
    document_id = "db02076e-989a-59cd-98d5-e24e15a0bd27"  # Replace with the actual document ID
    chunks = client.document_chunks(document_id=document_id)["results"]

    lead_chunk = {
        "extraction_id": "70c96e8f-e5d3-5912-b79b-13c5793f17b5",
        "document_id": "db02076e-989a-59cd-98d5-e24e15a0bd27",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
        # "text": "UNITED STATESSECURITIES AND EXCHANGE COMMISSION\nWashington, D.C. 20549\n____________________________________________ \nFORM\n 10-K____________________________________________ \n(Mark One)\n\n ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934For the fiscal year ended\n December 31, 2021OR",
        "metadata": {
            "version": "v0",
            "chunk_order": 0,
            "document_type": "txt",
        },
    }

    assert (
        len(chunks) >= 100
        and lead_chunk["document_id"] == chunks[0]["document_id"]
        and lead_chunk["user_id"] == chunks[0]["user_id"]
        and lead_chunk["collection_ids"][0] == chunks[0]["collection_ids"][0]
        # and "SECURITIES AND EXCHANGE COMMISSION" in chunks[0]["text"]
    )
    print("Document chunks test passed")
    print("~" * 100)


def test_delete_and_reingest_sample_file_sdk():
    print("Testing: Delete and re-ingest the sample file")

    # Delete the Aristotle document
    delete_response = client.delete(
        {"document_id": {"$eq": "db02076e-989a-59cd-98d5-e24e15a0bd27"}}
    )

    # Check if the deletion was successful
    if delete_response["results"] != {}:
        print("Delete and re-ingest test failed: Deletion unsuccessful")
        print("Delete response:", delete_response)
        sys.exit(1)

    print("Uber document deleted successfully")

    # Re-ingest the sample file
    file_paths = ["core/examples/data/aristotle.txt"]
    ingest_response = client.ingest_files(
        file_paths=file_paths, run_with_orchestration=False
    )

    if not ingest_response["results"]:
        print("Delete and re-ingest test failed: Re-ingestion unsuccessful")
        sys.exit(1)

    print("Sample file re-ingested successfully")

    print("Delete and re-ingest test passed")
    print("~" * 100)


def test_vector_search_sample_file_filter_sdk():
    print("Testing: Vector search over sample file")
    results = client.search(
        query="Who was Aristotle?",
        vector_search_settings={
            "filters": {
                "document_id": {"$eq": "db02076e-989a-59cd-98d5-e24e15a0bd27"}
            }
        },
    )["results"]["vector_search_results"]

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "extraction_id": "70c96e8f-e5d3-5912-b79b-13c5793f17b5",
        "document_id": "db02076e-989a-59cd-98d5-e24e15a0bd27",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "score": lambda x: 0.70 <= x <= 0.80,
    }
    print("lead_result = ", lead_result)
    compare_result_fields(lead_result, expected_lead_search_result)
    if "Aristotle" not in lead_result["text"]:
        print("Vector search test failed: Incorrect text")
        sys.exit(1)
    print("Vector search test passed")
    print("~" * 100)


def test_hybrid_search_sample_file_filter_sdk():
    print("Testing: Hybrid search over sample file")

    results = client.search(
        query="What were aristotles teachings?",
        vector_search_settings={
            "use_hybrid_search": True,
            "filters": {
                "document_id": {"$eq": "db02076e-989a-59cd-98d5-e24e15a0bd27"}
            },
        },
    )["results"]["vector_search_results"]

    if not results:
        print("Vector search test failed: No results returned")
        sys.exit(1)

    lead_result = results[0]
    expected_lead_search_result = {
        "extraction_id": "ca3d035b-6306-544b-abd3-7a84b9c78bfc",
        "document_id": "db02076e-989a-59cd-98d5-e24e15a0bd27",
        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
        "text": lambda x: "Aristotle" in x,
        "metadata": lambda x: "v0" == x["version"]
        and "txt" == x["document_type"]
        and "What were aristotles teachings?" == x["associated_query"]
        and 4 == x["semantic_rank"]
        and 2 == x["full_text_rank"],
    }
    print("lead_result = ", lead_result)
    compare_result_fields(lead_result, expected_lead_search_result)

    print("Hybrid search test passed")
    print("~" * 100)


def test_rag_response_sample_file_sdk():
    print("Testing: RAG query for sample file")
    response = client.rag(
        query="What was Aristotle's greatest contribution?",
        vector_search_settings={
            "filters": {
                "document_id": {"$eq": "db02076e-989a-59cd-98d5-e24e15a0bd27"}
            }
        },
    )["results"]["completion"]["choices"][0]["message"]["content"]

    expected_answer_0 = "Aristotle"
    expected_answer_1 = "logic"

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
        query="What was aristotles greatest contribution?",
        rag_generation_config={"stream": True},
        vector_search_settings={
            "filters": {
                "document_id": {"$eq": "db02076e-989a-59cd-98d5-e24e15a0bd27"}
            }
        },
    )

    response = ""
    for res in response:
        response += res
        print(res)

    expected_answer_0 = "Aristotle"
    expected_answer_1 = "logic"

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
            "filters": {
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
            "filters": {
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
            f"Agent query test failed: Expected answer(s) '{expected_answer_0}, {expected_answer_1}' not found in '{response}'"
        )
        sys.exit(1)

    print("Agent response stream test passed")
    print("~" * 100)


def test_user_registration_and_login():
    print("Testing: User registration and login")

    # Register a new user
    client.register("user_test@example.com", "password123")["results"]

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
        ["core/examples/data/aristotle_v2.txt"], run_with_orchestration=False
    )["results"]

    # Check the ingestion result
    if not ingestion_result:
        print("User document management test failed: Ingestion failed")
        sys.exit(1)

    ingested_document = ingestion_result[0]
    expected_ingestion_result = {
        # "message": "Ingestion task completed successfully.",
        # "task_id": None,
        "document_id": lambda x: len(x)
        == 36,  # Check if document_id is a valid UUID
    }
    compare_result_fields(ingested_document, expected_ingestion_result)
    assert "successfully" in ingested_document["message"]

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
        "title": "aristotle_v2.txt",
        "user_id": lambda x: len(x) == 36,  # Check if user_id is a valid UUID
        "document_type": "txt",
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
    search_query = "What was aristotle known for?"
    search_result = client.search(query=search_query)["results"]

    # Check the search result
    if not search_result["vector_search_results"]:
        print("User search test failed: No search results found")
        sys.exit(1)

    lead_search_result = search_result["vector_search_results"][0]
    expected_search_result = {
        "text": lambda x: "Aristotle" in x and "philo" in x,
        # "score": lambda x: 0.5 <= x <= 1.0,
    }
    compare_result_fields(lead_search_result, expected_search_result)

    # Perform a RAG query
    rag_query = "What was aristotle known for?"
    rag_result = client.rag(query=rag_query)["results"]

    # Check the RAG result
    if not rag_result["completion"]["choices"]:
        print("User RAG test failed: No RAG results found")
        sys.exit(1)

    rag_response = rag_result["completion"]["choices"][0]["message"]["content"]
    expected_rag_response = (
        lambda x: "Aristotle" in x and "Greek" in x and "philo" in x
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

    client.login("user_test@example.com", "password123")

    # Change password
    client.change_password("password123", "new_password")
    # Request password reset
    client.request_password_reset("user_test@example.com")

    # Confirm password reset (after user receives reset token)
    # reset_confirm_result = client.confirm_password_reset("reset_token_here", "password123")
    # print(f"Reset Confirm Result:\n{reset_confirm_result}")

    # Change password back to the original password
    client.change_password("new_password", "password123")

    print("User password management test passed")
    print("~" * 100)


def test_user_profile_management():
    print("Testing: User profile management")

    client.register("user_test123@example.com", "password123")
    client.login("user_test123@example.com", "password123")

    # Get user profile
    profile = client.user()["results"]

    # Update user profile
    update_result = client.update_user(
        user_id=str(profile["id"]), name="John Doe", bio="R2R enthusiast"
    )
    assert update_result["results"]["name"] == "John Doe"
    print("User profile management test passed")
    print("~" * 100)


def test_user_overview():
    print("Testing: User profile management")
    client.login("user_test@example.com", "password123")
    user_id = client.user()["results"]["id"]

    # Get user profile
    client.logout()
    overview = client.users_overview()

    found_user = False
    for user in overview["results"]:
        if user["user_id"] == user_id:
            found_user = True
            assert user["num_files"] == 1
            assert user["total_size_in_bytes"] > 0

    if not found_user:
        print("User overview test failed: User not found in the overview")
        sys.exit(1)

    print("User overview test passed")
    print("~" * 100)


def test_user_logout():
    print("Testing: User logout")

    client.login("user_test@example.com", "password123")
    logout_result = client.logout()

    assert logout_result["results"]["message"] == "Logged out successfully"
    print("User logout test passed")
    print("~" * 100)


def test_superuser_capabilities():
    print("Testing: Superuser capabilities")

    # Login as admin
    login_result = client.login("admin@example.com", "change_me_immediately")

    # Access users overview
    users_overview = client.users_overview()
    assert users_overview["total_entries"] > 0

    # Access system-wide logs
    logs = client.logs()
    assert len(logs["results"]) > 0

    # Perform analytics
    analytics_result = client.analytics(
        {"search_latencies": "search_latency"},
        {"search_latencies": ["basic_statistics", "search_latency"]},
    )
    assert analytics_result["results"]["analytics_data"]["search_latencies"]

    print("Superuser capabilities test passed")
    print("~" * 100)


def test_kg_create_graph_sample_file_sdk():
    print("Testing: KG create graph")

    create_graph_result = client.create_graph(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        run_type="run",
        run_with_orchestration=False,
    )

    print(create_graph_result)

    result = client.get_entities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        limit=1000,
        entity_level="document",
    )

    entities_list = [ele["name"] for ele in result["results"]["entities"]]

    print(entities_list)

    assert len(entities_list) >= 1
    assert "ARISTOTLE" in entities_list

    print("KG create graph test passed")
    print("~" * 100)


def test_kg_deduplicate_entities_sample_file_sdk():
    print("Testing: KG deduplicate entities")

    entities_deduplication_result = client.deduplicate_entities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        run_type="run",
    )

    if "queued" in entities_deduplication_result["results"]["message"]:
        time.sleep(45)

    response = client.get_entities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        limit=1000,
        entity_level="collection",
    )

    entities_list = [ele["name"] for ele in response["results"]["entities"]]

    assert len(entities_list) >= 1
    assert "ARISTOTLE" in entities_list

    # Check that there are no duplicates
    assert sorted(entities_list) == sorted(list(set(entities_list)))

    print("KG deduplicate entities test passed")
    print("~" * 100)


def test_kg_enrich_graph_sample_file_sdk():
    print("Testing: KG enrich graph")

    enrich_graph_result = client.enrich_graph(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        run_type="run",
        run_with_orchestration=False,
    )

    result = client.get_communities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    communities = result["results"]["communities"]
    assert len(communities) >= 1

    for community in communities:
        assert "community_number" in community
        assert "level" in community
        assert "collection_id" in community
        assert "name" in community

    print("KG enrich graph test passed")
    print("~" * 100)


def test_kg_search_sample_file_sdk():
    print("Testing: KG search")

    output = client.search(
        query="Who was aristotle?", kg_search_settings={"use_kg_search": True}
    )

    kg_search_results = output["results"]["kg_search_results"]
    print("kg_search_results = ", kg_search_results)
    assert len(kg_search_results) >= 1

    kg_search_result_present = False
    entities_found = False
    communities_found = False
    for result in kg_search_results:
        if "method" in result and result["method"] == "local":
            kg_search_result_present = True
        if "result_type" in result and result["result_type"] == "entity":
            entities_found = True
        if "result_type" in result and result["result_type"] == "community":
            communities_found = True

    assert kg_search_result_present, "No KG search result present"
    assert entities_found, "No entities found"
    assert communities_found, "No communities found"

    print("KG search test passed")
    print("~" * 100)


def test_kg_delete_graph_sample_file_sdk():
    print("Testing: KG delete graph")

    response = client.get_communities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    assert response["results"]["communities"] != []
    client.delete_graph_for_collection(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    response = client.get_communities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    assert response["results"]["communities"] == []

    response = client.get_entities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        entity_level="document",
    )

    assert response["results"]["entities"] != []

    print("KG delete graph test passed")
    print("~" * 100)


def test_kg_delete_graph_with_cascading_sample_file_sdk():
    print("Testing: KG delete graph with cascading")

    client.delete_graph_for_collection(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09", cascade=True
    )

    response = client.get_entities(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    assert response["results"]["entities"] == []

    response = client.get_triples(
        collection_id="122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
    )

    assert response["results"]["triples"] == []

    print("KG delete graph with cascading test passed")
    print("~" * 100)


def test_user_creates_collection():
    print("Testing: User creates a collection")

    # Register a new user
    client.register("collection_test@example.com", "password123")

    # Login as the new user
    client.login("collection_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing purposes"
    )

    # Check the collection creation result
    if not collection_result["results"]:
        print("User collection creation test failed: Collection not created")
        sys.exit(1)

    created_collection = collection_result["results"]
    expected_collection = {
        "collection_id": lambda x: len(x)
        == 36,  # Check if collection_id is a valid UUID
        "name": "Test Collection",
        "description": "Collection for testing purposes",
    }
    compare_result_fields(created_collection, expected_collection)

    print("User collection creation test passed")
    print("~" * 100)


def test_user_updates_collection():
    print("Testing: User updates a collection")

    # Register a new user
    client.register("collection_update_test@example.com", "password123")

    # Login as the new user
    client.login("collection_update_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing purposes"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Update the collection
    update_result = client.update_collection(
        collection_id,
        name="Updated Test Collection",
        description="Updated description for testing",
    )

    # Check the collection update result
    if not update_result["results"]:
        print("User collection update test failed: Collection not updated")
        sys.exit(1)

    updated_collection = update_result["results"]
    expected_updated_collection = {
        "collection_id": collection_id,
        "name": "Updated Test Collection",
        "description": "Updated description for testing",
    }
    compare_result_fields(updated_collection, expected_updated_collection)

    print("User collection update test passed")
    print("~" * 100)


def test_user_lists_collections():
    print("Testing: User lists collections")

    # Register a new user
    client.register("collection_list_test@example.com", "password123")

    # Login as the new user
    client.login("collection_list_test@example.com", "password123")

    # Create multiple collections
    client.create_collection(
        "Test Collection 1", "Collection 1 for testing purposes"
    )
    client.create_collection(
        "Test Collection 2", "Collection 2 for testing purposes"
    )
    client.create_collection(
        "Test Collection 3", "Collection 3 for testing purposes"
    )

    # List all collections
    passed = False
    try:
        collections_list = client.list_collections()
        passed = True
    except R2RException as e:
        pass
    if passed:
        raise Exception(
            "User collections list test failed: Expected an error for non super-user but listing succeeded"
        )

    client.login("admin@example.com", "change_me_immediately")
    collections_list = client.list_collections()

    # Check the collections list result
    if not collections_list["results"]:
        print("User collections list test failed: No collections found")
        sys.exit(1)

    expected_collections = [
        {
            "name": "Test Collection 1",
            "description": "Collection 1 for testing purposes",
        },
        {
            "name": "Test Collection 2",
            "description": "Collection 2 for testing purposes",
        },
        {
            "name": "Test Collection 3",
            "description": "Collection 3 for testing purposes",
        },
    ]

    for expected_collection in expected_collections:
        found = False
        for actual_collection in collections_list["results"]:
            if (
                actual_collection["name"] == expected_collection["name"]
                and actual_collection["description"]
                == expected_collection["description"]
            ):
                found = True
                break
        if not found:
            print(
                f"User collections list test failed: Expected collection '{expected_collection['name']}' not found"
            )
            sys.exit(1)

    print("User collections list test passed")
    print("~" * 100)


def test_user_collection_document_management():
    print("Testing: User collection document management")

    # Register a new user
    client.register("collection_doc_test@example.com", "password123")

    # Login as the new user
    client.login("collection_doc_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing document management"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Ingest the "aristotle.txt" file
    ingest_result = client.ingest_files(
        ["core/examples/data/aristotle_v2.txt"], run_with_orchestration=False
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to the collection
    assign_doc_result = client.assign_document_to_collection(
        document_id, collection_id
    )

    # Check the document assignment result
    if (
        not assign_doc_result["results"]["message"]
        == "Document assigned to collection successfully"
    ):
        print(
            "User collection document management test failed: Document assigned to collection successfully"
        )
        sys.exit(1)

    # List documents in the collection before removal
    docs_before_removal = client.documents_in_collection(collection_id)

    # Check if the document is present in the collection before removal
    if not any(
        doc["id"] == document_id for doc in docs_before_removal["results"]
    ):
        print(
            "User collection document management test failed: Document not found in the collection before removal"
        )
        sys.exit(1)

    # Remove the document from the collection
    remove_doc_result = client.remove_document_from_collection(
        document_id, collection_id
    )

    # Check the document removal result
    if not remove_doc_result["results"] == None:
        print(
            "User collection document management test failed: Document not removed from the collection"
        )
        sys.exit(1)

    # List documents in the collection after removal
    docs_after_removal = client.documents_in_collection(collection_id)

    # Check if the document is absent in the collection after removal
    if any(doc["id"] == document_id for doc in docs_after_removal["results"]):
        print(
            "User collection document management test failed: Document still present in the collection after removal"
        )
        sys.exit(1)

    print("User collection document management test passed")
    print("~" * 100)


def test_user_removes_document_from_collection():
    print("Testing: User removes a document from a collection")

    # Register a new user
    client.register("remove_doc_test@example.com", "password123")

    # Login as the new user
    client.login("remove_doc_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing document removal"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Ingest the "aristotle.txt" file
    ingest_result = client.ingest_files(
        ["core/examples/data/aristotle_v2.txt"], run_with_orchestration=True
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to the collection
    assign_doc_result = client.assign_document_to_collection(
        document_id, collection_id
    )

    # Check the document assignment result
    if (
        not assign_doc_result["results"]["message"]
        == "Document assigned to collection successfully"
    ):
        print(
            "User removes document from collection test failed: Document not assigned to the collection"
        )
        sys.exit(1)

    # Remove the document from the collection
    remove_doc_result = client.remove_document_from_collection(
        document_id, collection_id
    )

    # Check the document removal result
    if not remove_doc_result["results"] == None:
        print(
            "User removes document from collection test failed: Document not removed from the collection"
        )
        sys.exit(1)

    print("User removes document from collection test passed")
    print("~" * 100)


def test_user_lists_documents_in_collection():
    print("Testing: User lists documents in a collection")

    # Register a new user
    client.register("list_docs_test@example.com", "password123")

    # Login as the new user
    client.login("list_docs_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing document listing"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Ingest the "aristotle.txt" file
    ingest_result = client.ingest_files(
        ["core/examples/data/aristotle_v2.txt"], run_with_orchestration=True
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to the collection
    assign_doc_result = client.assign_document_to_collection(
        document_id, collection_id
    )

    # List documents in the collection before removal
    docs_before_removal = client.documents_in_collection(collection_id)

    # Check if the document is present in the collection before removal
    if not any(
        doc["id"] == document_id for doc in docs_before_removal["results"]
    ):
        print(
            "User lists documents in collection test failed: Document not found in the collection before removal"
        )
        sys.exit(1)

    # Remove the document from the collection
    remove_doc_result = client.remove_document_from_collection(
        document_id, collection_id
    )

    # List documents in the collection after removal
    docs_after_removal = client.documents_in_collection(collection_id)

    # Check if the document is absent in the collection after removal
    if any(
        doc["document_id"] == document_id
        for doc in docs_after_removal["results"]
    ):
        print(
            "User lists documents in collection test failed: Document still present in the collection after removal"
        )
        sys.exit(1)

    print("User lists documents in collection test passed")
    print("~" * 100)


def test_pagination_and_filtering():
    print("Testing: Pagination and filtering")

    # Register a new user
    client.register("pagination_test@example.com", "password123")

    # Login as the new user
    client.login("pagination_test@example.com", "password123")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing pagination and filtering"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Ingest multiple documents
    client.ingest_files(
        ["core/examples/data/aristotle.txt"], run_with_orchestration=True
    )
    client.ingest_files(
        ["core/examples/data/aristotle_v2.txt"], run_with_orchestration=True
    )

    documents_overview = client.documents_overview()["results"]
    client.assign_document_to_collection(
        documents_overview[0]["id"], collection_id
    )
    client.assign_document_to_collection(
        documents_overview[1]["id"], collection_id
    )

    # Test pagination for documents in collection
    paginated_docs = client.documents_in_collection(
        collection_id, offset=0, limit=2
    )
    if len(paginated_docs["results"]) != 2:
        print("Pagination test failed: Incorrect number of documents returned")
        sys.exit(1)

    # Test pagination for documents in collection
    paginated_docs = client.documents_in_collection(
        collection_id, offset=0, limit=1
    )
    if len(paginated_docs["results"]) != 1:
        print("Pagination test failed: Incorrect number of documents returned")
        sys.exit(1)

    # Test filtering for collections overview
    collections_overview = client.collections_overview(
        collection_ids=[collection_id]
    )
    if len(collections_overview["results"]) != 1:
        print(
            "Filtering test failed: Incorrect number of collections returned"
        )
        sys.exit(1)

    print("Pagination and filtering test passed")
    print("~" * 100)


def test_advanced_collection_management():
    print("Testing: Advanced collection management")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing advanced management"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Test collections overview
    collections_overview = client.collections_overview()
    if not any(
        c["collection_id"] == collection_id
        for c in collections_overview["results"]
    ):
        print("Collections overview test failed: Created collection not found")
        sys.exit(1)

    # Test deleting a collection
    delete_result = client.delete_collection(collection_id)
    if delete_result["results"] != None:
        print("Delete collection test failed: Unexpected result")
        sys.exit(1)

    print("Advanced collection management test passed")
    print("~" * 100)


def test_error_handling_and_edge_cases():
    print("Testing: Error handling and edge cases")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing error handling"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Test adding a non-existent user to a collection
    try:
        client.add_user_to_collection("non_existent_user_id", collection_id)
        print(
            "Error handling test failed: Expected an exception for non-existent user"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Test removing a user who is not a member of the collection
    try:
        client.remove_user_from_collection("non_member_user_id", collection_id)
        print(
            "Error handling test failed: Expected an exception for non-member user"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Test assigning a non-existent document to a collection
    try:
        client.assign_document_to_collection(
            "non_existent_document_id", collection_id
        )
        print(
            "Error handling test failed: Expected an exception for non-existent document"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Test removing a document that is not assigned to the collection
    try:
        client.remove_document_from_collection(
            "unassigned_document_id", collection_id
        )
        print(
            "Error handling test failed: Expected an exception for unassigned document"
        )
        sys.exit(1)
    except R2RException:
        pass

    print("Error handling and edge cases test passed")
    print("~" * 100)


def test_user_gets_collection_details():
    print("Testing: User gets collection details")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing get details"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Get collection details
    collection_details = client.get_collection(collection_id)

    # Check if the retrieved details match the created collection
    if collection_details["results"]["collection_id"] != collection_id:
        print("Get collection details test failed: Incorrect collection ID")
        sys.exit(1)

    print("Get collection details test passed")
    print("~" * 100)


def test_user_adds_user_to_collection():
    print("Testing: User adds user to a collection")
    client.login("admin@example.com", "change_me_immediately")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing add user"
    )
    collection_id = collection_result["results"]["collection_id"]

    # # Register a new user
    client.register("add_user_test1@example.com", "password123")
    client.login("add_user_test1@example.com", "password123")["results"]
    user_id = client.user()["results"]["id"]

    # login as admin
    client.login("admin@example.com", "change_me_immediately")
    # Add the user to the collection
    add_user_result = client.add_user_to_collection(user_id, collection_id)

    print("add_user_result = ", add_user_result)
    # Check if the user was added successfully
    if add_user_result["results"] != None:
        print(
            "Add user to collection test failed: User not added to the collection"
        )
        sys.exit(1)

    print("Add user to collection test passed")
    print("~" * 100)


def test_user_removes_user_from_collection():
    print("Testing: User removes user from a collection")

    client.login("admin@example.com", "change_me_immediately")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing remove user"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Register a new user
    client.register("remove_user_test@example.com", "password123")
    client.login("remove_user_test@example.com", "password123")["results"]
    user_id = client.user()["results"]["id"]

    client.login("admin@example.com", "change_me_immediately")

    # Add the user to the collection
    client.add_user_to_collection(user_id, collection_id)

    # Remove the user from the collection
    remove_user_result = client.remove_user_from_collection(
        user_id, collection_id
    )

    # Check if the user was removed successfully
    if remove_user_result["results"] != None:
        print(
            "Remove user from collection test failed: User not removed from the collection"
        )
        sys.exit(1)

    print("Remove user from collection test passed")
    print("~" * 100)


def test_user_lists_users_in_collection():
    print("Testing: User lists users in a collection")
    client.login("admin@example.com", "change_me_immediately")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing list users"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Register a new user
    client.register("list_users_test@example.com", "password123")
    client.login("list_users_test@example.com", "password123")["results"]
    user_id = client.user()["results"]["id"]

    client.login("admin@example.com", "change_me_immediately")

    # Add the user to the collection
    client.add_user_to_collection(user_id, collection_id)

    # List users in the collection
    users_in_collection = client.get_users_in_collection(collection_id)

    # Check if the user is present in the collection
    if not any(
        user["id"] == user_id for user in users_in_collection["results"]
    ):
        print(
            "List users in collection test failed: User not found in the collection"
        )
        sys.exit(1)

    print("List users in collection test passed")
    print("~" * 100)


def test_user_gets_collections_for_user():
    print("Testing: User gets collections for a user")
    client.login("admin@example.com", "change_me_immediately")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing get user collections"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Register a new user
    client.register("get_user_collections_test@example.com", "password123")
    client.login("get_user_collections_test@example.com", "password123")

    user_id = client.user()["results"]["id"]

    client.login("admin@example.com", "change_me_immediately")
    # Add the user to the collection
    client.add_user_to_collection(user_id, collection_id)

    # Get collections for the user
    user_collections = client.user_collections(user_id)

    # Check if the collection is present in the user's collections
    if not any(
        collection["collection_id"] == collection_id
        for collection in user_collections["results"]
    ):
        print(
            "Get collections for user test failed: Collection not found in user's collections"
        )
        sys.exit(1)

    print("Get collections for user test passed")
    print("~" * 100)


def test_user_gets_collections_for_document():
    print("Testing: User gets collections for a document")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing get document collections"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Ingest a document
    ingest_result = client.ingest_files(
        ["core/examples/data/pg_essay_1.html"], run_with_orchestration=False
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to the collection
    client.assign_document_to_collection(document_id, collection_id)

    # Get collections for the document
    document_collections = client.document_collections(document_id)["results"]
    # Check if the collection is present in the document's collections
    if collection_id not in [
        ele["collection_id"] for ele in document_collections
    ]:
        print(
            "Get collections for document test failed: Collection not found in document's collections"
        )
        sys.exit(1)

    print("Get collections for document test passed")
    print("~" * 100)


def test_user_permissions():
    print("Testing: User permissions for collection management")

    # Register a new user
    client.register("permissions_test22@example.com", "password123")
    client.login("permissions_test22@example.com", "password123")

    collection = client.create_collection(
        "Test Collection", "Collection for testing permissions"
    )

    client.register("permissions_test_222@example.com", "password123")
    client.login("permissions_test_222@example.com", "password123")

    # Try to delete the collection as a user who is not the owner
    try:
        client.delete_collection(collection["results"]["collection_id"])
        print(
            "User permissions test failed: User able to delete a collection they do not own"
        )
        sys.exit(1)
    except R2RException:
        pass

    print("User permissions test passed")
    print("~" * 100)


def test_collection_user_interactions():
    print("Testing: Collection user interactions")

    # Register a new user and create a collection
    client.register("collection_owner@example.com", "password123")
    client.login("collection_owner@example.com", "password123")
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing user interactions"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Register another user
    client.register("user_interactions_test@example.com", "password123")
    client.login("user_interactions_test@example.com", "password123")
    user_id = client.user()["results"]["id"]

    # Ingest a document
    client.login("collection_owner@example.com", "password123")
    ingest_result = client.ingest_files(
        ["core/examples/data/aristotle.txt"], run_with_orchestration=False
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to the collection
    assignment_result = client.assign_document_to_collection(
        document_id, collection_id
    )

    # Try to access the document as a user not in the collection
    client.login("user_interactions_test@example.com", "password123")
    try:
        client.document_chunks(document_id)
        print(
            "Collection user interactions test failed: User able to access document in a collection they are not a member of"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Add the user to the collection
    client.login("collection_owner@example.com", "password123")
    client.add_user_to_collection(user_id, collection_id)

    # Try to access the document as a user in the collection
    client.login("user_interactions_test@example.com", "password123")
    document_chunks = client.document_chunks(document_id)
    if not document_chunks["results"]:
        print(
            "Collection user interactions test failed: User unable to access document in a collection they are a member of"
        )
        sys.exit(1)

    print("Collection user interactions test passed")
    print("~" * 100)


def test_collection_document_interactions():
    print("Testing: Collection document interactions")

    # Create two new collections
    collection1_result = client.create_collection(
        "Test Collection 1", "Collection 1 for testing document interactions"
    )
    collection1_id = collection1_result["results"]["collection_id"]

    collection2_result = client.create_collection(
        "Test Collection 2", "Collection 2 for testing document interactions"
    )
    collection2_id = collection2_result["results"]["collection_id"]

    # Ingest a document
    ingest_result = client.ingest_files(
        ["core/examples/data/aristotle.txt"], run_with_orchestration=False
    )

    document_id = ingest_result["results"][0]["document_id"]

    # Assign the document to both collections
    client.assign_document_to_collection(document_id, collection1_id)
    client.assign_document_to_collection(document_id, collection2_id)

    # Get collections for the document
    document_collections = client.document_collections(document_id)

    test_collection_ids = [collection1_id, collection2_id]
    if not all(
        collection_id
        in [c["collection_id"] for c in document_collections["results"]]
        for collection_id in test_collection_ids
    ):
        print(
            "Collection document interactions test failed: Document not assigned to both test collections"
        )
        sys.exit(1)

    print("Collection document interactions test passed")
    print("~" * 100)


def test_error_handling():
    print("Testing: Error handling for collections")

    # Create a new collection
    collection_result = client.create_collection(
        "Test Collection", "Collection for testing error handling"
    )
    collection_id = collection_result["results"]["collection_id"]

    # Try to add a non-existent user to the collection
    try:
        client.add_user_to_collection("non_existent_user_id", collection_id)
        print(
            "Error handling test failed: Expected an exception for adding a non-existent user to a collection"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Try to remove a user who is not a member of the collection
    try:
        client.remove_user_from_collection("non_member_user_id", collection_id)
        print(
            "Error handling test failed: Expected an exception for removing a non-member user from a collection"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Try to assign a non-existent document to the collection
    try:
        client.assign_document_to_collection(
            "non_existent_document_id", collection_id
        )
        print(
            "Error handling test failed: Expected an exception for assigning a non-existent document to a collection"
        )
        sys.exit(1)
    except R2RException:
        pass

    # Try to remove a document that is not assigned to the collection
    try:
        client.remove_document_from_collection(
            "unassigned_document_id", collection_id
        )
        print(
            "Error handling test failed: Expected an exception for removing an unassigned document from a collection"
        )
        sys.exit(1)
    except R2RException:
        pass

    print("Error handling test passed")
    print("~" * 100)


def test_conversation_history_sdk():
    print("Testing: Conversation history")

    # Start a conversation
    messages = [
        {"role": "user", "content": "Who was Aristotle?"},
        {
            "role": "assistant",
            "content": "Aristotle was a Greek philosopher and scientist who lived from 384 BC to 322 BC. He was a student of Plato and later became the tutor of Alexander the Great. Aristotle is considered one of the most influential thinkers in Western philosophy and his works covered a wide range of subjects including logic, metaphysics, ethics, biology, and politics.",
        },
        {
            "role": "user",
            "content": "What were some of his major contributions to philosophy?",
        },
    ]

    response = client.agent(
        messages=messages,
        rag_generation_config={"stream": False},
    )["results"]

    conversation = client.get_conversation(response["conversation_id"])
    messages.append(
        {"role": "assistant", "content": response["messages"][-1]["content"]}
    )

    # Check if the conversation history is maintained
    if len(conversation["results"]) != 4:
        print(
            "Conversation history test failed: Incorrect number of messages in the conversation"
        )
        sys.exit(1)

    for i, (message_id, message) in enumerate(conversation["results"]):
        if (
            message["role"] != messages[i]["role"]
            or message["content"] != messages[i]["content"]
        ):
            print(
                "Conversation history test failed: Incorrect message content or role"
            )
            sys.exit(1)

    # pass another message
    message = {
        "role": "user",
        "content": "What were some of his major contributions to philosophy?",
    }
    messages.append(message)

    response = client.agent(
        message=message,
        conversation_id=response["conversation_id"],
        rag_generation_config={"stream": False},
    )["results"]
    messages.append(
        {"role": "assistant", "content": response["messages"][-1]["content"]}
    )

    conversation = client.get_conversation(response["conversation_id"])

    # Check if the conversation history is maintained
    if len(conversation["results"]) != 6:
        print(
            "Conversation history test failed: Incorrect number of messages in the conversation"
        )
        sys.exit(1)

    for i, (message_id, message) in enumerate(conversation["results"]):
        if i < len(messages):
            if (
                message["role"] != messages[i]["role"]
                or message["content"] != messages[i]["content"]
            ):
                print(
                    "Conversation history test failed: Incorrect message content or role"
                )
                sys.exit(1)
        else:
            if message["role"] != "assistant":
                print(
                    "Conversation history test failed: Incorrect message role for assistant response"
                )
                sys.exit(1)
            if response["messages"][-1]["content"] != message["content"]:
                print(
                    "Conversation history test failed: Incorrect assistant response content"
                )
                sys.exit(1)

    print("Conversation history test passed")
    print("~" * 100)


def test_ingest_chunks():
    print("Testing: Ingest chunks")

    client.ingest_chunks(
        chunks=[
            {
                # extraction_id should be 21acd7c0-fe60-572e-89b1-3ae71861bbb3
                "text": "Hello, world!",
            },
            {
                # extraction_id should be 7c1871cd-0f6a-52c1-84d8-3365c29251b3
                "text": "Hallo, Welt!",
            },
            {
                # extraction_id should be bccdb72f-ac9f-5708-81eb-b4d781ed9fe2
                "text": "Szia, világ!",
            },
            {
                # extraction_id should be 0d3d0fdd-5a13-55a7-8f42-8443f3ad7fbc
                "text": "Dzień dobry, świecie!",
            },
        ],
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672",
        metadata={
            "Language 1": "English",
            "Language 2": "German",
            "Language 3": "Hungarian",
            "Language 4": "Polish",
        },
        run_with_orchestration=False,
    )

    ingest_chunks_response = client.document_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672"
    )

    # Assert that the extraction_id is correct
    assert (
        ingest_chunks_response["results"][0]["extraction_id"]
        == "21acd7c0-fe60-572e-89b1-3ae71861bbb3"
    )
    assert (
        ingest_chunks_response["results"][1]["extraction_id"]
        == "7c1871cd-0f6a-52c1-84d8-3365c29251b3"
    )
    assert (
        ingest_chunks_response["results"][2]["extraction_id"]
        == "bccdb72f-ac9f-5708-81eb-b4d781ed9fe2"
    )
    assert (
        ingest_chunks_response["results"][3]["extraction_id"]
        == "0d3d0fdd-5a13-55a7-8f42-8443f3ad7fbc"
    )


def test_update_chunks():
    print("Testing: Update chunk")

    client.update_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672",
        extraction_id="21acd7c0-fe60-572e-89b1-3ae71861bbb3",
        text="Goodbye, world!",
    )

    client.update_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672",
        extraction_id="7c1871cd-0f6a-52c1-84d8-3365c29251b3",
        text="Auf Wiedersehen, Welt!",
    )

    client.update_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672",
        extraction_id="bccdb72f-ac9f-5708-81eb-b4d781ed9fe2",
        text="Viszlát, világ!",
    )

    client.update_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672",
        extraction_id="0d3d0fdd-5a13-55a7-8f42-8443f3ad7fbc",
        text="Dobranoc, świecie!",
    )

    ingest_chunks_response = client.document_chunks(
        document_id="82346fd6-7479-4a49-a16a-88b5f91a3672"
    )

    # Assert that the text has been updated
    assert ingest_chunks_response["results"][0]["text"] == "Goodbye, world!"
    assert (
        ingest_chunks_response["results"][1]["text"]
        == "Auf Wiedersehen, Welt!"
    )
    assert ingest_chunks_response["results"][2]["text"] == "Viszlát, világ!"
    assert ingest_chunks_response["results"][3]["text"] == "Dobranoc, świecie!"

    # Assert that the metadata has been maintained
    assert (
        ingest_chunks_response["results"][0]["metadata"]["Language 1"]
        == "English"
    )


def test_delete_chunks():
    print("Testing: Delete chunks")

    client.delete(
        {"extraction_id": {"$eq": "21acd7c0-fe60-572e-89b1-3ae71861bbb3"}}
    )
    client.delete(
        {"extraction_id": {"$eq": "7c1871cd-0f6a-52c1-84d8-3365c29251b3"}}
    )
    client.delete(
        {"extraction_id": {"$eq": "bccdb72f-ac9f-5708-81eb-b4d781ed9fe2"}}
    )
    client.delete(
        {"extraction_id": {"$eq": "0d3d0fdd-5a13-55a7-8f42-8443f3ad7fbc"}}
    )
    try:
        client.document_chunks(
            document_id="82346fd6-7479-4a49-a16a-88b5f91a3672"
        )
    except R2RException as e:
        assert e.status_code == 404


def test_get_all_prompts():
    print("Testing: Get All Prompts")

    response = client.get_all_prompts()

    # Test basic structure
    assert isinstance(response, dict)
    assert "results" in response
    assert "prompts" in response["results"]

    # Test prompts dictionary
    prompts = response["results"]["prompts"]
    assert isinstance(prompts, dict)

    # Test that we have at least some expected prompt types
    expected_prompt_types = {
        "default_system",
        "rag_agent",
        "hyde",
        "default_rag",
    }
    assert expected_prompt_types.issubset(set(prompts.keys()))

    # Test structure of individual prompt entries
    for _, prompt_data in prompts.items():
        assert isinstance(prompt_data, dict)
        required_fields = {
            "name",
            "prompt_id",
            "template",
            "created_at",
            "updated_at",
            "input_types",
        }

        assert all(field in prompt_data for field in required_fields)

        # Test field types
        assert isinstance(prompt_data["name"], str)
        assert isinstance(prompt_data["template"], str)
        assert isinstance(prompt_data["created_at"], str)
        assert isinstance(prompt_data["updated_at"], str)
        assert isinstance(prompt_data["input_types"], dict)

        # Test timestamp format
        for timestamp in [
            prompt_data["created_at"],
            prompt_data["updated_at"],
        ]:
            assert timestamp.endswith("Z")
            assert (
                "T" in timestamp
            )  # ISO format contains T between date and time


def test_get_prompt():
    print("Testing: Get Prompt")

    response = client.get_prompt("default_system")

    print(response)

    # Test basic structure
    assert isinstance(response, dict)
    assert "results" in response
    assert "You are a helpful agent." in response["results"]["message"]


def test_add_prompt():
    print("Testing: Add Prompt")

    # Test adding a new prompt
    prompt_data = {
        "name": "test_prompt",
        "template": "This is a test prompt with {input_var}",
        "input_types": {"input_var": "string"},
    }

    add_result = client.add_prompt(
        name=prompt_data["name"],
        template=prompt_data["template"],
        input_types=prompt_data["input_types"],
    )["results"]

    print("add_result = ", add_result)
    # Verify the prompt was added successfully
    assert prompt_data["name"] in add_result["message"]

    print("Add prompt test passed")
    print("~" * 100)


def test_update_prompt():
    print("Testing: Update Prompt")

    # Update an existing prompt
    updated_template = "This is an updated test prompt with {input_var}"
    updated_input_types = {"input_var": "string", "new_var": "integer"}

    update_result = client.update_prompt(
        name="test_prompt",
        template=updated_template,
        input_types=updated_input_types,
    )["results"]

    # Verify the prompt was updated successfully
    assert "test_prompt" in update_result["message"]

    get_prompt_result = client.get_prompt("test_prompt")["results"]
    assert "an updated" in get_prompt_result["message"]

    # Test partial updates
    template_only_update = "Template only update with {input_var}"
    template_update_result = client.update_prompt(
        name="test_prompt", template=template_only_update
    )["results"]

    assert "test_prompt" in template_update_result["message"]

    print("Update prompt test passed")
    print("~" * 100)


def test_get_prompt():
    print("Testing: Get Prompt")

    # Test getting a prompt without inputs
    basic_result = client.get_prompt("test_prompt")["results"]
    assert "message" in basic_result

    # Test getting a prompt with inputs
    inputs = {"input_var": "test value"}
    result_with_inputs = client.get_prompt("test_prompt", inputs=inputs)[
        "results"
    ]
    assert "message" in result_with_inputs
    assert "test value" in result_with_inputs["message"]

    print("Get prompt test passed")
    print("~" * 100)


def test_get_all_prompts():
    print("Testing: Get All Prompts")

    result = client.get_all_prompts()["results"]

    # Verify structure of the response
    assert "prompts" in result
    prompts = result["prompts"]

    # Verify our test prompt is in the list
    test_prompt = prompts.get("test_prompt")
    assert test_prompt is not None
    assert test_prompt["name"] == "test_prompt"
    assert "template" in test_prompt
    assert "input_types" in test_prompt
    assert "prompt_id" in test_prompt
    assert "created_at" in test_prompt
    assert "updated_at" in test_prompt

    # Verify required system prompts exist
    required_prompts = {"default_system", "rag_agent", "hyde"}
    assert all(prompt in prompts for prompt in required_prompts)

    print("Get all prompts test passed")
    print("~" * 100)


def test_delete_prompt():
    print("Testing: Delete Prompt")

    # First, verify the prompt exists
    all_prompts_before = client.get_all_prompts()["results"]["prompts"]
    assert "test_prompt" in all_prompts_before

    # Delete the prompt
    delete_result = client.delete_prompt("test_prompt")["results"]
    assert delete_result is None

    # Verify the prompt was deleted
    all_prompts_after = client.get_all_prompts()["results"]["prompts"]
    assert "test_prompt" not in all_prompts_after

    # Test deleting a non-existent prompt
    try:
        client.delete_prompt("non_existent_prompt")
        assert False, "Expected an error when deleting non-existent prompt"
    except Exception as e:
        assert "not found" in str(e).lower()

    print("Delete prompt test passed")
    print("~" * 100)


def test_prompt_error_handling():
    print("Testing: Prompt Error Handling")

    # # Test adding a prompt with invalid input types
    # try:
    #     client.add_prompt(
    #         name="invalid_prompt",
    #         template="Test template",
    #         input_types={"var": "invalid_type"},
    #     )
    #     assert False, "Expected an error for invalid input type"
    # except Exception as e:
    #     assert "invalid input type" in str(e).lower()

    # # Test adding a prompt with invalid template
    # try:
    #     client.add_prompt(
    #         name="invalid_prompt",
    #         template="Template with {undefined_var}",
    #         input_types={"other_var": "string"},
    #     )
    #     assert False, "Expected an error for undefined template variable"
    # except Exception as e:
    #     assert "undefined variable" in str(e).lower()

    # Test updating a non-existent prompt
    try:
        client.update_prompt(
            name="non_existent_prompt", template="New template"
        )
        assert False, "Expected an error when updating non-existent prompt"
    except Exception as e:
        assert "not found" in str(e).lower()

    print("Prompt error handling test passed")
    print("~" * 100)


def test_prompt_access_control():
    print("Testing: Prompt Access Control")

    # Create a new non-admin user
    client.register("prompt_test_user@example.com", "password123")
    client.login("prompt_test_user@example.com", "password123")

    # Test that non-admin user can't add prompts
    try:
        client.add_prompt(
            name="unauthorized_prompt",
            template="Test template",
            input_types={"var": "string"},
        )
        assert False, "Expected an error for unauthorized prompt creation"
    except Exception as e:
        print("e = ", e)
        assert "superuser" in str(e).lower()

    # Test that non-admin user can't update system prompts
    try:
        client.update_prompt(
            name="default_system", template="Modified system prompt"
        )
        assert False, "Expected an error for unauthorized prompt update"
    except Exception as e:
        print("e = ", e)
        assert "superuser" in str(e).lower()

    # Test that non-admin user can't delete prompts
    try:
        client.delete_prompt("default_system")
        assert False, "Expected an error for unauthorized prompt deletion"
    except Exception as e:
        print("e = ", e)
        assert "superuser" in str(e).lower()

    # # Verify that non-admin user can still get prompts
    # get_result = client.get_prompt("default_system")
    # assert "message" in get_result["results"]
    client.logout()
    print("Prompt access control test passed")
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
