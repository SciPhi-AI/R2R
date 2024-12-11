import argparse
import asyncio
import sys
import time
import uuid

from r2r import GenerationConfig, Message, R2RClient, R2RException, SearchMode


def assert_http_error(condition, message):
    if not condition:
        print("Test failed:", message)
        sys.exit(1)


def test_search_basic_mode():
    print("Testing: Basic mode search")
    # Just a simple query, expecting some results if the system is populated.
    resp = client.retrieval.search(query="Aristotle", search_mode="basic")
    # Check structure
    assert_http_error("results" in resp, "No results field in search response")
    print("Basic mode search test passed")
    print("~" * 100)


def test_search_advanced_mode_with_filters():
    print("Testing: Advanced mode search with filters")
    # In a real scenario, use a known document_id or filter
    filters = {"document_type": {"$eq": "txt"}}
    resp = client.retrieval.search(
        query="Philosophy",
        search_mode="advanced",
        search_settings={"filters": filters, "limit": 5},
    )
    assert_http_error("results" in resp, "No results in advanced mode search")
    print("Advanced mode search with filters test passed")
    print("~" * 100)


def test_search_custom_mode():
    print("Testing: Custom mode search")
    # Custom search with semantic search enabled and a limit
    resp = client.retrieval.search(
        query="Greek philosophers",
        search_mode="custom",
        search_settings={"use_semantic_search": True, "limit": 3},
    )
    assert_http_error("results" in resp, "No results in custom mode search")
    print("Custom mode search test passed")
    print("~" * 100)


def test_rag_query():
    print("Testing: RAG query")
    # Just do a standard RAG query without streaming
    resp = client.retrieval.rag(
        query="Summarize Aristotle's contributions to logic",
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 3},
    )["results"]

    print("response:", resp)
    # # Check response structure
    # if isinstance(resp, dict):
    #     assert_http_error("answer" in resp and "sources" in resp, "RAG response missing 'answer' or 'sources'")
    # else:
    #     # Unexpected streaming or different type
    #     print("Expected dict response for non-streaming RAG")
    #     sys.exit(1)
    print("RAG query test passed")
    print("~" * 100)


def test_rag_stream_query():
    print("Testing: RAG query with streaming")
    # Streamed responses come as an async generator from the SDK
    # We'll just iterate a few chunks and confirm no errors occur
    resp = client.retrieval.rag(
        query="Detail the philosophical schools Aristotle influenced",
        rag_generation_config={"stream": True, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 2},
    )

    # resp is an async generator
    # For simplicity, run in synchronous manner using run_until_complete if needed
    import asyncio

    async def consume_stream():
        count = 0
        async for chunk in resp:
            count += 1
            if count > 2:  # just read a couple of chunks
                break
        return count

    count = asyncio.run(consume_stream())
    assert_http_error(count > 0, "No chunks received from streamed RAG query")
    print("RAG streaming query test passed")
    print("~" * 100)


def test_agent_query():
    print("Testing: Agent query")
    # Single-turn agent interaction
    msg = Message(role="user", content="What is Aristotle known for?")
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 3},
    )

    if isinstance(resp, dict):
        # Expecting something like a wrapped response with "results"
        # The current code returns a list of messages or a response with "results"
        assert_http_error(
            "results" in resp, "Agent response missing 'results'"
        )
        assert_http_error(
            len(resp["results"]) > 0, "No messages returned by agent"
        )
    else:
        print("Agent query did not return a dict")
        sys.exit(1)
    print("Agent query test passed")
    print("~" * 100)


def test_agent_query_stream():
    print("Testing: Agent query with streaming")
    msg = Message(
        role="user", content="Explain Aristotle's logic in a stepwise manner."
    )
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={"stream": True, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
    )

    import asyncio

    async def consume_stream():
        count = 0
        async for chunk in resp:
            count += 1
            if count > 2:
                break
        return count

    count = asyncio.run(consume_stream())
    assert_http_error(count > 0, "No streaming chunks received from agent")
    print("Agent streaming query test passed")
    print("~" * 100)


def test_completion():
    print("Testing: Completion")
    # Basic conversation
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "What about Italy?"},
    ]
    resp = client.retrieval.completion(
        messages, generation_config={"max_tokens": 50}
    )
    assert_http_error(
        "results" in resp, "Completion response missing 'results'"
    )
    content = resp["results"]["choices"][0]["message"]["content"]

    assert_http_error(len(content) > 0, "Completion response missing content")
    # assert_http_error(
    #     "content" in resp["results"], "No 'content' in completion result"
    # )
    print("Completion test passed")
    print("~" * 100)


def test_embedding():
    print("Testing: Embedding")
    text = "Who is Aristotle?"
    resp = client.retrieval.embedding(text=text)["results"]

    assert_http_error(len(resp) > 0, "No embedding vector returned")
    print("Embedding test passed")
    print("~" * 100)


def test_error_handling():
    print("Testing: Error handling on missing query")
    # Missing query should raise an error
    try:
        client.retrieval.search(query=None)  # type: ignore
        print("Expected error for missing query, got none.")
        sys.exit(1)
    except R2RException as e:
        # Check for a 422 or appropriate error code
        print("Caught expected error for missing query:", str(e))
    print("Error handling test passed")
    print("~" * 100)


def create_client(base_url):
    return R2RClient(base_url)


def test_no_results_scenario():
    print("Testing: No results scenario")
    # Query a nonsense term that should return no results
    resp = client.retrieval.search(query="aslkfjaldfjal", search_mode="basic")
    # Expect no results
    results = resp.get("results", [])
    assert_http_error(
        len(results) == 0, "Expected no results for nonsense query"
    )
    print("No results scenario test passed")
    print("~" * 100)


def test_pagination_limit_zero():
    print("Testing: Pagination with limit=1")
    client.documents.create(
        chunks=["a", "b", "c"],  # multi-chunks
    )
    resp = client.retrieval.search(
        query="Aristotle", search_mode="basic", search_settings={"limit": 1}
    )["results"]
    results = resp["chunk_search_results"]
    assert len(results) == 1, "Expected one result with limit=1"


def test_pagination_offset():
    print("Testing: Pagination offset beyond total results")
    # First, do a normal search to find out total_entries
    resp0 = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={"limit": 1, "offset": 0},
    )["results"]
    resp1 = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={"limit": 1, "offset": 1},
    )["results"]
    assert (
        resp0["chunk_search_results"][0]["text"]
        != resp1["chunk_search_results"][0]["text"]
    ), "Offset beyond results should return different results"


def test_rag_task_prompt_override():
    print("Testing: RAG with task_prompt_override")
    # Provide a unique prompt override that should appear in the final answer
    custom_prompt = """
    Answer the query given immediately below given the context which follows later. Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context. Pay close attention to the title of each given source to ensure it is consistent with the query.


    ### Query:

    {query}


    ### Context:
    {context}

    You must end your answer with the phrase: [END-TEST-PROMPT]"""
    resp = client.retrieval.rag(
        query="Tell me about Aristotle",
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        task_prompt_override=custom_prompt,
    )

    answer = resp["results"]["completion"]["choices"][0]["message"]["content"]
    # Check if our unique phrase is in the answer
    assert_http_error(
        "[END-TEST-PROMPT]" in answer,
        "Custom prompt override not reflected in RAG answer",
    )
    print("RAG task_prompt_override test passed")
    print("~" * 100)


def test_agent_conversation_id():
    print("Testing: Agent with conversation_id")
    # Start a conversation
    # conversation_id = str(uuid.uuid4())
    conversation = client.conversations.create()["results"]
    conversation_id = conversation["id"]
    msg = Message(role="user", content="What is Aristotle known for?")
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        conversation_id=conversation_id,
    )

    # Expect results
    results = resp.get("results", [])
    assert_http_error(
        len(results) > 0, "No results from agent with conversation_id"
    )
    # Send a follow-up message in the same conversation
    msg2 = Message(role="user", content="Can you elaborate more?")
    resp2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        conversation_id=conversation_id,
    )
    # Expect some continuity; we mainly check for no error and some reply
    results2 = resp2.get("results", [])
    assert_http_error(
        len(results2) > 0,
        "No results from agent in second turn of conversation",
    )
    print("Agent conversation_id test passed")
    print("~" * 100)


def _setup_collection_with_documents(client):
    """
    Create a collection and add multiple documents with diverse metadata fields.
    """
    # 1. Create a new collection
    collection_name = f"Test Collection {uuid.uuid4()}"
    # collection_resp: WrappedCollectionResponse = await collections_sdk.create(name=collection_name)
    # collection_id = collection_resp.results["id"]
    collection_id = client.collections.create(name=collection_name)["results"][
        "id"
    ]

    # 2. Add documents with different metadata fields
    # Assume `documents_sdk.create` allows setting text and metadata
    # Example metadata fields:
    # - numeric field: rating
    # - array field: tags
    # - string field: category
    # - full-text unique keyword in text: "unique_philosopher"

    docs = [
        {
            "text": "Aristotle was a Greek philosopher who studied under Plato.",
            "metadata": {
                "rating": 5,
                "tags": ["philosophy", "greek"],
                "category": "ancient",
            },
        },
        {
            "text": "Socrates is considered a founder of Western philosophy.",
            "metadata": {
                "rating": 3,
                "tags": ["philosophy", "classical"],
                "category": "ancient",
            },
        },
        {
            "text": "Rene Descartes was a French philosopher. unique_philosopher",
            "metadata": {
                "rating": 8,
                "tags": ["rationalism", "french"],
                "category": "modern",
            },
        },
        {
            "text": "Immanuel Kant, a German philosopher, influenced Enlightenment thought.",
            "metadata": {
                "rating": 7,
                "tags": ["enlightenment", "german"],
                "category": "modern",
            },
        },
    ]

    doc_ids = []
    for doc in docs:
        # documents_sdk.create returns a doc with an id
        result = client.documents.create(
            raw_text=doc["text"], metadata=doc["metadata"]
        )["results"]
        doc_id = result["document_id"]
        doc_ids.append(doc_id)

        # Add the document to the collection
        client.collections.add_document(collection_id, doc_id)

    # Optionally, if extraction/indexing is needed:
    # await collections_sdk.extract(collection_id, settings={"run_mode": "run"})
    print("collection_id = ", collection_id)
    print("doc_ids = ", doc_ids)
    return collection_id, doc_ids


def test_complex_filters_and_fulltext():
    # Set up data
    collection_id, doc_ids = _setup_collection_with_documents(client)

    # We'll run a series of searches with various filters:
    # Wait briefly if asynchronous indexing is required
    # await asyncio.sleep(5)

    # 1. Test a simple $gt filter on a numeric field (rating > 5)
    filters = {"rating": {"$gt": 5}}
    resp = client.retrieval.search(
        query="a",
        search_mode=SearchMode.custom,
        search_settings={"use_semantic_search": True, "filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    print("results = ", results)
    # Expect documents with rating > 5 (i.e., rating=7 and rating=8)
    # We have two docs with rating 7 and 8
    assert_http_error(
        len(results) == 2,
        f"Expected 2 docs with rating > 5, got {len(results)}",
    )

    # 2. Test an $in filter on a string field (category in [ancient, modern])
    filters = {"metadata.category": {"$in": ["ancient", "modern"]}}
    resp = client.retrieval.search(
        query="b",
        search_mode=SearchMode.custom,
        search_settings={"use_semantic_search": True, "filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    # All docs have category either 'ancient' or 'modern', so we expect all 4
    assert_http_error(
        len(results) == 4, f"Expected all 4 docs, got {len(results)}"
    )

    # # 3. Test $overlap on an array field (tags overlap ["philosophy"])
    # filters = {
    #     "metadata.tags": {
    #         "$overlaps": ["philosophy"]
    #     }
    # }
    # resp = client.retrieval.search(query="c", search_mode=SearchMode.custom, search_settings={"use_semantic_search": True, "filters": filters})["results"]
    # results = resp["chunk_search_results"]
    # The first two documents have "philosophy" in tags
    # assert_http_error(len(results) == 2, f"Expected 2 docs overlapping 'philosophy', got {len(results)}")

    # 4. Test compound $and conditions: rating > 5 AND category=modern
    filters = {
        "$and": [
            {"metadata.rating": {"$gt": 5}},
            {"metadata.category": {"$eq": "modern"}},
        ]
    }
    resp = client.retrieval.search(
        query="d",
        search_mode=SearchMode.custom,
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    # The docs with rating > 5 and category=modern are Descartes (rating=8, modern) and Kant (rating=7, modern)
    assert_http_error(
        len(results) == 2,
        f"Expected 2 docs (Descartes, Kant), got {len(results)}",
    )

    # 5. Test $or conditions: category=ancient OR category=modern but rating<5
    filters = {
        "$or": [
            {"metadata.category": {"$eq": "ancient"}},
            {"metadata.rating": {"$lt": 5}},
        ]
    }
    resp = client.retrieval.search(
        query="e",
        search_mode=SearchMode.custom,
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    # category=ancient matches Aristotle and Socrates
    # rating<5 matches Socrates again (rating=3)
    # So total distinct docs: Aristotle, Socrates (2 docs)
    assert_http_error(
        len(results) == 2,
        f"Expected Aristotle and Socrates, got {len(results)}",
    )

    # 6. Test $contains on array field (tags contains 'french')
    filters = {"metadata.tags": {"$contains": ["french"]}}
    resp = client.retrieval.search(
        query="f",
        search_mode=SearchMode.custom,
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    # Only Descartes has 'french' in tags
    assert_http_error(
        len(results) == 1, f"Expected only Descartes, got {len(results)}"
    )

    # 7. Test full-text search by searching for "unique_philosopher"
    # Only Descartes doc contains "unique_philosopher"
    resp = client.retrieval.search(
        query="unique_philosopher",
        search_mode=SearchMode.custom,
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
        },
    )["results"]
    results = resp["chunk_search_results"]
    assert_http_error(
        len(results) == 1,
        f"Expected only the Descartes document, got {len(results)}",
    )

    print("All complex filter and full-text search tests passed")


def test_complex_nested_filters():
    print("Testing: Complex nested AND/OR filters")

    # Assume we have documents that differ in category, rating, and tags.
    # For example:
    # Doc1: category=ancient, rating=5, tags=["philosophy","greek"]
    # Doc2: category=ancient, rating=3, tags=["philosophy","classical"]
    # Doc3: category=modern, rating=8, tags=["rationalism","french"]
    # Doc4: category=modern, rating=7, tags=["enlightenment","german"]

    # Complex filter: ((category=ancient OR rating<5) AND (tags contains 'philosophy'))
    # This should return docs that are ancient or have rating<5, and also have 'philosophy' in tags.
    # That would be Doc1 and Doc2.

    filters = {
        "$and": [
            {
                "$or": [
                    {"metadata.category": {"$eq": "ancient"}},
                    {"metadata.rating": {"$lt": 5}},
                ]
            },
            {"metadata.tags": {"$contains": ["philosophy"]}},
        ]
    }

    resp = client.retrieval.search(
        query="complex",
        search_mode="custom",
        search_settings={
            "filters": filters
        },  # , "use_semantic_search": False}
    )["results"]

    results = resp["chunk_search_results"]
    # Expect 2 docs: Aristotle and Socrates.
    assert_http_error(
        len(results) == 2, f"Expected 2 docs, got {len(results)}"
    )

    print("Complex nested filters test passed")
    print("~" * 100)


def test_invalid_operator():
    print("Testing: Invalid operator in filters")

    # Using a deliberately invalid operator "$like" which is not supported.
    filters = {"metadata.category": {"$like": "%ancient%"}}  # invalid operator

    try:
        client.retrieval.search(
            query="abc",
            search_mode="custom",
            search_settings={"filters": filters},
        )
        print("Expected error for invalid operator, got none.")
        sys.exit(1)
    except R2RException as e:
        # Expect some error indicating unsupported operator
        print("Caught expected error for invalid operator:", str(e))

    print("Invalid operator test passed")
    print("~" * 100)


def test_filters_no_match():
    print("Testing: Filters with no matches")

    # $in test with values that no document has:
    # Suppose no doc has category 'nonexistent'
    filters = {"metadata.category": {"$in": ["nonexistent"]}}

    resp = client.retrieval.search(
        query="noresults",
        search_mode="custom",
        search_settings={
            "filters": filters
        },  # , "use_semantic_search": False}
    )["results"]

    results = resp["chunk_search_results"]
    # Expect no results
    assert_http_error(
        len(results) == 0, f"Expected 0 docs, got {len(results)}"
    )

    print("Filters no match test passed")
    print("~" * 100)


def test_pagination_extremes():
    print("Testing: Pagination with large offset and checking page_info")

    # First, get total_entries from a normal query
    base_resp = client.retrieval.search(query="Aristotle", search_mode="basic")
    total_entries = base_resp.get("page_info", {}).get("total_entries", 0)

    # Query with offset beyond total_entries
    offset = total_entries + 10
    resp = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={"limit": 10, "offset": offset},
    )["results"]
    results = resp["chunk_search_results"]
    print("results = ", results)
    # Expect no results
    assert_http_error(
        len(results) == 0,
        f"Expected no results at large offset, got {len(results)}",
    )

    # # Confirm page_info makes sense
    # page_info = resp.get("page_info", {})
    # assert_http_error(page_info.get("has_next") == False, "Expected has_next=False at large offset")
    # assert_http_error(page_info.get("current_page") == (offset // 10) + 1, "Current page not computed correctly")

    print("Pagination extremes test passed")
    print("~" * 100)


def test_full_text_stopwords():
    print("Testing: Full-text search with stopwords")

    # If the system supports stopwords, searching common words like "the" or "is"
    # might return either all documents or none. We want to ensure no errors and logical behavior.
    resp = client.retrieval.search(
        query="the",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 5,
        },
    )
    # Just check no error and some results or possibly empty results are returned gracefully.
    results = resp.get("results", [])
    # It's okay if results are empty or not; we just don't want errors.
    assert_http_error(
        "results" in resp, "No results field in stopword query response"
    )

    print("Full-text stopwords test passed")
    print("~" * 100)


def test_full_text_non_ascii():
    print("Testing: Full-text search with non-ASCII characters")

    # Insert or ensure a document has non-ASCII text, e.g., "Aristotélēs"
    # Query that exact term to see if full-text search handles it.
    resp = client.retrieval.search(
        query="Aristotélēs",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 3,
        },
    )
    results = resp.get("results", [])
    # If such a doc exists, ensure it's returned. If not, ensure no error and empty results.
    # This test mainly checks the system doesn’t fail on non-ASCII.
    assert_http_error(
        "results" in resp, "No results field in non-ASCII query response"
    )

    print("Full-text non-ASCII test passed")
    print("~" * 100)


def test_missing_fields():
    print("Testing: Filters on missing fields")

    # If we try a filter on `metadata.someNonExistentField`, no doc should match.
    filters = {"metadata.someNonExistentField": {"$eq": "anything"}}

    resp = client.retrieval.search(
        query="missingfield",
        search_mode="custom",
        search_settings={"filters": filters},
    )["results"]

    results = resp["chunk_search_results"]
    assert_http_error(
        len(results) == 0,
        f"Expected 0 docs for a non-existent field, got {len(results)}",
    )

    print("Missing fields test passed")
    print("~" * 100)


def test_rag_with_large_context():
    print("Testing: RAG with large context")

    # If possible, have a doc with a large amount of text and multiple chunks.
    # This checks that RAG still picks correct chunks and no errors occur.
    # Just confirm it returns a sensible answer and no error.
    resp = client.retrieval.rag(
        query="Explain the contributions of Kant in detail",
        rag_generation_config={"stream": False, "max_tokens": 200},
        search_settings={"use_semantic_search": True, "limit": 10},
    )

    # Check structure
    results = resp.get("results", {})
    assert_http_error(
        "completion" in results, "RAG large context missing 'completion'"
    )
    completion = results["completion"]["choices"][0]["message"]["content"]
    assert_http_error(
        len(completion) > 0, "RAG large context returned empty answer"
    )

    print("RAG with large context test passed")
    print("~" * 100)


def test_agent_long_conversation():
    print("Testing: Agent multi-turn conversation")

    # Start a conversation
    conversation = client.conversations.create()["results"]
    conversation_id = conversation["id"]

    # Turn 1
    msg1 = Message(role="user", content="What were Aristotle's main ideas?")
    resp1 = client.retrieval.agent(
        message=msg1,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert_http_error(
        "results" in resp1, "No results in first turn of conversation"
    )

    # Turn 2, follow up question
    msg2 = Message(
        role="user", content="How did these ideas influence modern philosophy?"
    )
    resp2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert_http_error(
        "results" in resp2, "No results in second turn of conversation"
    )

    # Turn 3, changing topic to confirm no break:
    msg3 = Message(role="user", content="Now tell me about Descartes.")
    resp3 = client.retrieval.agent(
        message=msg3,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert_http_error(
        "results" in resp3, "No results in third turn of conversation"
    )

    # Just ensure no errors and some continuity. The agent should not fail when topic changes.
    print("Agent long conversation test passed")
    print("~" * 100)


def test_filter_by_document_type():
    print("Testing: Agent multi-turn conversation")

    try:
        result = client.documents.create(chunks=["a", "b", "c"])["results"]
    except Exception as e:
        pass

    filters = {"document_type": {"$eq": "txt"}}

    resp = client.retrieval.search(
        query="a", search_settings={"filters": filters}
    )["results"]
    results = resp["chunk_search_results"]
    if len(results) == 0:
        print("No results found for filter by document type")
        raise Exception("No results found for filter by document type")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="R2R SDK Retrieval Integration Tests"
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
