import uuid

import pytest

from core.base import Message, SearchMode
from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def config():

    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and log in as a superuser."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


def test_search_basic_mode(client: R2RClient):
    results = client.retrieval.search(query="Aristotle",
                                      search_mode="basic").results
    assert results is not None, "No results field in search response"


def test_search_advanced_mode_with_filters(client: R2RClient):
    filters = {"metadata.document_type": {"$eq": "txt"}}
    results = client.retrieval.search(
        query="Philosophy",
        search_mode="advanced",
        search_settings={
            "filters": filters,
            "limit": 5
        },
    ).results
    assert results is not None, "No results in advanced mode search"


def test_search_custom_mode(client: R2RClient):
    results = client.retrieval.search(
        query="Greek philosophers",
        search_mode="custom",
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
    ).results
    assert results is not None, "No results in custom mode search"


def test_rag_query(client: R2RClient):
    results = client.retrieval.rag(
        query="Summarize Aristotle's contributions to logic",
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
    ).results
    assert results.completion is not None, "RAG response missing 'completion'"


def test_rag_with_filter(client: R2RClient):
    # Ensure a doc with metadata.tier='test' is created
    # generate a random string
    suffix = str(uuid.uuid4())
    client.documents.create(
        raw_text=
        f"Aristotle was a Greek philosopher, contributions to philosophy were in logic, {suffix}.",
        metadata={"tier": "test"},
    )
    results = client.retrieval.rag(
        query="What were aristotle's contributions to philosophy?",
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "filters": {
                "metadata.tier": {
                    "$eq": "test"
                }
            },
            "use_semantic_search": True,
            "limit": 3,
        },
    ).results
    assert results.completion is not None, "RAG response missing 'completion'"


def test_rag_stream_query(client: R2RClient):
    resp = client.retrieval.rag(
        query="Detail the philosophical schools Aristotle influenced",
        rag_generation_config={
            "stream": True,
            "max_tokens": 50
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 2
        },
    )

    # Consume a few chunks from the async generator

    def consume_stream():
        count = 0
        for chunk in resp:
            count += 1
            if count > 1:
                break
        return count

    # count = asyncio.run(consume_stream())
    count = consume_stream()
    assert count > 0, "No chunks received from streamed RAG query"


def test_agent_query(client: R2RClient):
    msg = Message(role="user", content="What is Aristotle known for?")
    results = client.retrieval.agent(
        message=msg,
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
    ).results
    assert results is not None, "Agent response missing 'results'"
    assert len(results.messages) > 0, "No messages returned by agent"


def test_agent_query_stream(client: R2RClient):
    msg = Message(role="user", content="Explain Aristotle's logic in steps.")
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={
            "stream": True,
            "max_tokens": 50
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
    )

    def consume_stream():
        count = 0
        for chunk in resp:
            count += 1
            if count > 1:
                break
        return count

    count = consume_stream()  # asyncio.run(consume_stream())
    assert count > 0, "No streaming chunks received from agent"


def test_completion(client: R2RClient):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "What is the capital of France?"
        },
        {
            "role": "assistant",
            "content": "The capital of France is Paris."
        },
        {
            "role": "user",
            "content": "What about Italy?"
        },
    ]
    resp = client.retrieval.completion(
        messages,
        generation_config={
            "max_tokens": 50,
            "model": "openai/gpt-4o"
        },
    )
    assert resp.results is not None, "Completion response missing 'results'"
    assert resp.results.choices is not None, "No choices in completion result"


def test_embedding(client: R2RClient):
    text = "Who is Aristotle?"
    resp = client.retrieval.embedding(text=text).results
    assert len(resp) > 0, "No embedding vector returned"


def test_error_handling(client: R2RClient):
    # Missing query should raise an error
    with pytest.raises(R2RException) as exc_info:
        client.retrieval.search(query=None)  # type: ignore
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected validation error for missing query"


def test_no_results_scenario(client: R2RClient):
    results = client.retrieval.search(
        query="aslkfjaldfjal",
        search_mode="custom",
        search_settings={
            "limit": 5,
            "use_semantic_search": False,
            "use_fulltext_search": True,
        },
    ).results
    results = results.chunk_search_results
    assert len(results) == 0, "Expected no results for nonsense query"


def test_pagination_limit_one(client: R2RClient):
    client.documents.create(chunks=[
        "a" + " " + str(uuid.uuid4()),
        "b" + " " + str(uuid.uuid4()),
        "c" + " " + str(uuid.uuid4()),
    ])
    results = client.retrieval.search(query="Aristotle",
                                      search_mode="basic",
                                      search_settings={
                                          "limit": 1
                                      }).results
    assert len(results.chunk_search_results) == 1, (
        "Expected one result with limit=1")


def test_pagination_offset(client: R2RClient):
    resp0 = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={
            "limit": 1,
            "offset": 0
        },
    ).results
    resp1 = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={
            "limit": 1,
            "offset": 1
        },
    ).results

    assert (resp0.chunk_search_results[0].text
            != resp1.chunk_search_results[0].text
            ), "Offset should return different results"


def test_rag_task_prompt(client: R2RClient):
    custom_prompt = """
    Answer the query given immediately below given the context. End your answer with: [END-TEST-PROMPT]

    ### Query:
    {query}

    ### Context:
    {context}
    """
    results = client.retrieval.rag(
        query="Tell me about Aristotle",
        rag_generation_config={"stream": False}, # , "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        task_prompt=custom_prompt,
    ).results
    answer = results.completion
    assert "[END-TEST-PROMPT]" in answer, (
        "Custom prompt override not reflected in RAG answer")


def test_agent_conversation_id(client: R2RClient):
    conversation_id = client.conversations.create().results.id
    msg = Message(role="user", content="What is Aristotle known for?")
    results = client.retrieval.agent(
        message=msg,
        rag_generation_config={
            "stream": False,
            "max_tokens": 50
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
        conversation_id=str(conversation_id),
    ).results
    assert len(
        results.messages) > 0, ("No results from agent with conversation_id")

    msg2 = Message(role="user", content="Can you elaborate more?")
    results2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={
            "stream": False,
            "max_tokens": 50
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 3
        },
        conversation_id=str(conversation_id),
    ).results
    assert len(results2.messages) > 0, (
        "No results from agent in second turn of conversation")


def test_complex_filters_and_fulltext(client: R2RClient, test_collection):
    # collection_id, doc_ids = _setup_collection_with_documents(client)

    user_id = client.users.me().results.id
    # rating > 5
    # include  owner id and collection ids to make robust against other database interactions from other users
    filters = {
        "rating": {
            "$gt": 5
        },
        "owner_id": {
            "$eq": str(user_id)
        },
        "collection_ids": {
            "$overlap": [str(test_collection["collection_id"])]
        },
    }
    results = client.retrieval.search(
        query="a",
        search_mode=SearchMode.custom,
        search_settings={
            "use_semantic_search": True,
            "filters": filters
        },
    ).results
    results = results.chunk_search_results
    assert len(results) == 2, (
        f"Expected 2 docs with rating > 5, got {len(results)}")

    # category in [ancient, modern]
    filters = {
        "metadata.category": {
            "$in": ["ancient", "modern"]
        },
        "owner_id": {
            "$eq": str(user_id)
        },
        "collection_ids": {
            "$overlap": [str(test_collection["collection_id"])]
        },
    }

    results = client.retrieval.search(
        query="b",
        search_mode=SearchMode.custom,
        search_settings={
            "use_semantic_search": True,
            "filters": filters
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 4, (
        f"Expected all 4 docs, got {len(chunk_search_results)}")

    # rating > 5 AND category=modern
    filters = {
        "$and": [
            {
                "metadata.rating": {
                    "$gt": 5
                }
            },
            {
                "metadata.category": {
                    "$eq": "modern"
                }
            },
            {
                "owner_id": {
                    "$eq": str(user_id)
                }
            },
            {
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                }
            },
        ],
    }
    results = client.retrieval.search(
        query="d",
        search_mode=SearchMode.custom,
        search_settings={
            "filters": filters
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 2, (
        f"Expected 2 modern docs with rating>5, got {len(chunk_search_results)}"
    )

    results = client.retrieval.search(
        query="unique_philosopher",
        search_mode=SearchMode.custom,
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "owner_id": {
                    "$eq": str(user_id)
                },
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                },
            },
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 1, (
        f"Expected 1 doc for unique_philosopher, got {len(chunk_search_results)}"
    )


def test_complex_nested_filters(client: R2RClient, test_collection):
    # Setup docs
    # _setup_collection_with_documents(client)

    # ((category=ancient OR rating<5) AND tags contains 'philosophy')
    filters = {
        "$and": [
            {
                "$or": [
                    {
                        "metadata.category": {
                            "$eq": "ancient"
                        }
                    },
                    {
                        "metadata.rating": {
                            "$lt": 5
                        }
                    },
                ]
            },
            {
                "metadata.tags": {
                    "$contains": ["philosophy"]
                }
            },
            {
                "owner_id": {
                    "$eq": str(client.users.me().results.id)
                }
            },
            {
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                }
            },
        ],
    }

    results = client.retrieval.search(
        query="complex",
        search_settings={
            "filters": filters
        },
    ).results
    chunk_search_results = results.chunk_search_results

    assert (
        len(chunk_search_results) == 2
    ), f"Expected 2 docs, got {len(chunk_search_results)}"


def test_filters_no_match(client: R2RClient):
    filters = {"metadata.category": {"$in": ["nonexistent"]}}
    results = client.retrieval.search(
        query="noresults",
        search_mode="custom",
        search_settings={
            "filters": filters
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 0, (
        f"Expected 0 docs, got {len(chunk_search_results)}")


def test_pagination_extremes(client: R2RClient):
    total_entries = client.chunks.list().total_entries

    offset = total_entries + 100
    results = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={
            "limit": 10,
            "offset": offset
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 0, (
        f"Expected no results at large offset, got {len(chunk_search_results)}"
    )


def test_full_text_stopwords(client: R2RClient):
    resp = client.retrieval.search(
        query="the",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 5,
        },
    )
    assert resp.results is not None, (
        "No results field in stopword query response")


def test_full_text_non_ascii(client: R2RClient):
    resp = client.retrieval.search(
        query="Aristotélēs",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 3,
        },
    )
    assert resp.results is not None, (
        "No results field in non-ASCII query response")


def test_missing_fields(client: R2RClient):
    filters = {"metadata.someNonExistentField": {"$eq": "anything"}}
    results = client.retrieval.search(
        query="missingfield",
        search_mode="custom",
        search_settings={
            "filters": filters
        },
    ).results
    chunk_search_results = results.chunk_search_results
    assert len(chunk_search_results) == 0, (
        f"Expected 0 docs for a non-existent field, got {len(chunk_search_results)}"
    )


def test_rag_with_large_context(client: R2RClient):
    results = client.retrieval.rag(
        query="Explain the contributions of Kant in detail",
        rag_generation_config={
            "stream": False,
            "max_tokens": 200
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 10
        },
    ).results
    assert results.completion is not None, (
        "RAG large context missing 'completion'")
    completion = results.completion
    assert len(completion) > 0, "RAG large context returned empty answer"


def test_agent_long_conversation(client: R2RClient):
    conversation_id = client.conversations.create().results.id

    msg1 = Message(role="user", content="What were Aristotle's main ideas?")
    resp1 = client.retrieval.agent(
        message=msg1,
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 5
        },
        conversation_id=str(conversation_id),
    )
    assert resp1.results is not None, (
        "No results in first turn of conversation")

    msg2 = Message(role="user",
                   content="How did these ideas influence modern philosophy?")
    resp2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 5
        },
        conversation_id=str(conversation_id),
    )
    assert resp2.results is not None, (
        "No results in second turn of conversation")

    msg3 = Message(role="user", content="Now tell me about Descartes.")
    resp3 = client.retrieval.agent(
        message=msg3,
        rag_generation_config={
            "stream": False,
            "max_tokens": 100
        },
        search_settings={
            "use_semantic_search": True,
            "limit": 5
        },
        conversation_id=str(conversation_id),
    )
    assert resp3.results is not None, (
        "No results in third turn of conversation")


def test_filter_by_document_type(client: R2RClient):
    random_suffix = str(uuid.uuid4())
    client.documents.create(chunks=[
        f"a {random_suffix}",
        f"b {random_suffix}",
        f"c {random_suffix}",
    ])
    filters = {"document_type": {"$eq": "txt"}}
    results = client.retrieval.search(query="a",
                                      search_settings={
                                          "filters": filters
                                      }).results
    chunk_search_results = results.chunk_search_results
    assert (
        len(chunk_search_results) > 0
    ), "No results found for filter by document type"


def test_search_hyde_mode(client: R2RClient):
    """
    Integration test for HyDE search. We create a doc, then query with
    search_strategy='hyde'. We expect the system to generate hypothetical docs,
    embed them, and return chunk search results.
    """
    # 1) Create a test doc containing "Aristotle" text
    suffix = str(uuid.uuid4())
    client.documents.create(
        chunks=[
            f"Aristotle. Fulltext test doc. {uuid.uuid4()}",
            f"Plato. Fulltext test doc. {uuid.uuid4()}",
            f"Socrates. Fulltext test doc. {uuid.uuid4()}",
            f"Pythagoras. Fulltext test doc. {uuid.uuid4()}",
            f"Euclid. Fulltext test doc. {uuid.uuid4()}",
        ],
        metadata={"category": "test_hyde_fulltext"},
    )

    # 2) Perform a HyDE search
    resp = client.retrieval.search(
        query="Aristotle achievements?",
        search_mode="custom",  # or 'basic'—the key is in search_settings below
        search_settings={
            "search_strategy": "hyde",
            "use_semantic_search": True,
            "limit": 5,
            # If you want multiple hypothetical docs:
            "num_sub_queries": 5,
        },
    )

    # 3) Validate the results
    results = resp.results
    assert results is not None, "No results returned by HyDE search"
    assert (
        len(results.chunk_search_results) == 25
    ), "Expected 25 chunk search results"
    chunk_results = results.chunk_search_results
    # We can't guarantee you have actual matches in your DB,
    # but we can at least confirm the structure is correct.
    # If your DB has a doc referencing "Aristotle," we might get hits:
    assert (
        chunk_results is not None
    ), "No chunk_search_results in HyDE search response"
    # Optionally you can assert chunk_results is not empty if you expect a match
    # but that depends on your environment.


def test_search_rag_fusion_mode(client: R2RClient):
    """
    Integration test for RAG-Fusion search. For now, your code is a placeholder
    that calls _basic_search. But this ensures it doesn't error out and returns
    valid results.
    """
    suffix = str(uuid.uuid4())
    client.documents.create(
        raw_text=f"Plato was another Greek philosopher. RAGFusionTestDoc: {suffix}",
        metadata={"category": "test_rag_fusion"},
    )

    # 2) Perform a RAG-Fusion search
    resp = client.retrieval.search(
        query="Plato's contributions?",
        search_mode="custom",
        search_settings={
            "search_strategy": "rag_fusion",
            "use_semantic_search": True,
            "limit": 5,
            # "num_sub_queries": 3 if you actually implement it
        },
    )

    # 3) Validate the results
    results = resp.results
    assert results is not None, "No results returned by RAG-Fusion search"
    chunk_results = results.chunk_search_results
    assert chunk_results is not None, "No chunk_search_results for RAG-Fusion"
    # Possibly check if chunk_results is not empty if you have data
    assert (
        len(results.chunk_search_results) == 5
    ), "Expected 5 chunk search results"


def test_rag_fusion_mode_with_subqueries(client: R2RClient):
    """
    If/when you actually implement multi-subquery logic for rag_fusion,
    you'd pass 'num_sub_queries': 3, etc.
    Currently it's a placeholder, but let's just confirm the service doesn't error out.
    """
    resp = client.retrieval.search(
        query="What are Plato's main dialogues?",
        search_mode="custom",
        search_settings={
            "search_strategy": "rag_fusion",
            "use_semantic_search": True,
            "limit": 5,
            "num_sub_queries": 3,
        },
    )
    results = resp.results
    assert (
        results is not None
    ), "No results returned by RAG-Fusion with subqueries"
    # When fully implemented, you can check if the chunk results are non-empty, etc.

def test_collection_id_filters(client: R2RClient):
    """
    Test both collection_id and collection_ids filters to ensure they work properly
    with the updated filters.py code.
    """
    # Create a new collection for this test
    collection_response = client.collections.create(
        name=f"Collection Filter Test {uuid.uuid4()}"
    )
    collection_id = collection_response.results.id

    # Create a second collection to verify filtering works correctly
    other_collection_response = client.collections.create(
        name=f"Other Collection {uuid.uuid4()}"
    )
    other_collection_id = other_collection_response.results.id

    # Add unique identifier to track the test documents
    unique_marker = str(uuid.uuid4())

    # Create documents in the first collection
    for i in range(3):
        doc_response = client.documents.create(
            raw_text=f"Test document {i} for collection filter test with marker {unique_marker}",
            metadata={"test_group": "collection_filter_test"}
        )
        doc_id = doc_response.results.document_id

        # Add document to the first collection
        client.collections.add_document(
            id=collection_id,
            document_id=doc_id
        )

    # Create a document in the second collection
    doc_response = client.documents.create(
        raw_text=f"Test document in second collection with marker {unique_marker}",
        metadata={"test_group": "collection_filter_test"}
    )
    doc_id = doc_response.results.document_id

    # Add document to the second collection
    client.collections.add_document(
        id=other_collection_id,
        document_id=doc_id
    )

    # Wait for indexing to complete
    import time
    time.sleep(2)

    # Test 1: Using collection_id filter (singular form)
    results1 = client.retrieval.search(
        query=unique_marker,
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "collection_id": {"$eq": str(collection_id)}
            }
        }
    ).results

    # Test 2: Using collection_ids filter (plural form)
    results2 = client.retrieval.search(
        query=unique_marker,
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "collection_ids": {"$overlap": [str(collection_id)]}
            }
        }
    ).results

    # Test 3: Using $in operator with collection_id
    results3 = client.retrieval.search(
        query=unique_marker,
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "collection_id": {"$in": [str(collection_id)]}
            }
        }
    ).results

    # Test 4: Using both collections with $overlap
    results4 = client.retrieval.search(
        query=unique_marker,
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "collection_ids": {"$overlap": [str(collection_id), str(other_collection_id)]}
            }
        }
    ).results

    # Test 5: Using a non-existent collection ID
    results5 = client.retrieval.search(
        query=unique_marker,
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "collection_id": {"$eq": str(uuid.uuid4())}
            }
        }
    ).results

    # Verify results
    # First three tests should return exactly 3 chunks from the first collection
    assert len(results1.chunk_search_results) == 3, f"collection_id $eq filter returned {len(results1.chunk_search_results)} results, expected 3"
    assert len(results2.chunk_search_results) == 3, f"collection_ids $overlap filter returned {len(results2.chunk_search_results)} results, expected 3"
    assert len(results3.chunk_search_results) == 3, f"collection_id $in filter returned {len(results3.chunk_search_results)} results, expected 3"

    # Test 4 should return all 4 chunks from both collections
    assert len(results4.chunk_search_results) == 4, f"collection_ids $overlap with multiple IDs returned {len(results4.chunk_search_results)} results, expected 4"

    # Test 5 should return no results for non-existent collection
    assert len(results5.chunk_search_results) == 0, f"Non-existent collection ID filter returned {len(results5.chunk_search_results)} results, expected 0"

    # Clean up
    client.collections.delete(id=collection_id)
    client.collections.delete(id=other_collection_id)
