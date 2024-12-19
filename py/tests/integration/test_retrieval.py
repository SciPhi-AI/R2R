import uuid

import pytest

from r2r import Message, R2RClient, R2RException, SearchMode


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


def test_search_basic_mode(client):
    resp = client.retrieval.search(query="Aristotle", search_mode="basic")
    assert "results" in resp, "No results field in search response"


def test_search_advanced_mode_with_filters(client):
    filters = {"metadata.document_type": {"$eq": "txt"}}
    resp = client.retrieval.search(
        query="Philosophy",
        search_mode="advanced",
        search_settings={"filters": filters, "limit": 5},
    )
    assert "results" in resp, "No results in advanced mode search"


def test_search_custom_mode(client):
    resp = client.retrieval.search(
        query="Greek philosophers",
        search_mode="custom",
        search_settings={"use_semantic_search": True, "limit": 3},
    )
    assert "results" in resp, "No results in custom mode search"


def test_rag_query(client):
    resp = client.retrieval.rag(
        query="Summarize Aristotle's contributions to logic",
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 3},
    )["results"]
    assert "completion" in resp, "RAG response missing 'completion'"


def test_rag_with_filter(client):
    # Ensure a doc with metadata.tier='test' is created
    # generate a random string
    suffix = str(uuid.uuid4())
    client.documents.create(
        raw_text=f"Aristotle was a Greek philosopher, contributions to philosophy were in logic, {suffix}.",
        metadata={"tier": "test"},
    )
    resp = client.retrieval.rag(
        query="What were aristotle's contributions to philosophy?",
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={
            "filters": {"metadata.tier": {"$eq": "test"}},
            "use_semantic_search": True,
            "limit": 3,
        },
    )["results"]
    assert "completion" in resp, "RAG response missing 'completion'"


def test_rag_stream_query(client):
    resp = client.retrieval.rag(
        query="Detail the philosophical schools Aristotle influenced",
        rag_generation_config={"stream": True, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 2},
    )

    # Consume a few chunks from the async generator
    import asyncio

    async def consume_stream():
        count = 0
        async for chunk in resp:
            count += 1
            if count > 1:
                break
        return count

    count = asyncio.run(consume_stream())
    assert count > 0, "No chunks received from streamed RAG query"


def test_agent_query(client):
    msg = Message(role="user", content="What is Aristotle known for?")
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 3},
    )
    assert "results" in resp, "Agent response missing 'results'"
    assert len(resp["results"]) > 0, "No messages returned by agent"


def test_agent_query_stream(client):
    msg = Message(role="user", content="Explain Aristotle's logic in steps.")
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
            if count > 1:
                break
        return count

    count = asyncio.run(consume_stream())
    assert count > 0, "No streaming chunks received from agent"


def test_completion(client):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "What about Italy?"},
    ]
    resp = client.retrieval.completion(
        messages, generation_config={"max_tokens": 50}
    )
    assert "results" in resp, "Completion response missing 'results'"
    assert "choices" in resp["results"], "No choices in completion result"


def test_embedding(client):
    text = "Who is Aristotle?"
    resp = client.retrieval.embedding(text=text)["results"]
    assert len(resp) > 0, "No embedding vector returned"


def test_error_handling(client):
    # Missing query should raise an error
    with pytest.raises(R2RException) as exc_info:
        client.retrieval.search(query=None)  # type: ignore
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected validation error for missing query"


def test_no_results_scenario(client):
    resp = client.retrieval.search(
        query="aslkfjaldfjal",
        search_mode="custom",
        search_settings={
            "limit": 5,
            "use_semantic_search": False,
            "use_fulltext_search": True,
        },
    )
    results = resp.get("results", {}).get("chunk_search_results", [])
    assert len(results) == 0, "Expected no results for nonsense query"


def test_pagination_limit_one(client):
    client.documents.create(
        chunks=[
            "a" + " " + str(uuid.uuid4()),
            "b" + " " + str(uuid.uuid4()),
            "c" + " " + str(uuid.uuid4()),
        ]
    )
    resp = client.retrieval.search(
        query="Aristotle", search_mode="basic", search_settings={"limit": 1}
    )["results"]
    assert (
        len(resp["chunk_search_results"]) == 1
    ), "Expected one result with limit=1"


def test_pagination_offset(client):
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
    ), "Offset should return different results"


def test_rag_task_prompt_override(client):
    custom_prompt = """
    Answer the query given immediately below given the context. End your answer with: [END-TEST-PROMPT]

    ### Query:
    {query}

    ### Context:
    {context}
    """
    resp = client.retrieval.rag(
        query="Tell me about Aristotle",
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        task_prompt_override=custom_prompt,
    )
    answer = resp["results"]["completion"]["choices"][0]["message"]["content"]
    assert (
        "[END-TEST-PROMPT]" in answer
    ), "Custom prompt override not reflected in RAG answer"


def test_agent_conversation_id(client):
    conversation_id = client.conversations.create()["results"]["id"]
    msg = Message(role="user", content="What is Aristotle known for?")
    resp = client.retrieval.agent(
        message=msg,
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        conversation_id=conversation_id,
    )
    assert (
        len(resp.get("results", [])) > 0
    ), "No results from agent with conversation_id"

    msg2 = Message(role="user", content="Can you elaborate more?")
    resp2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={"stream": False, "max_tokens": 50},
        search_settings={"use_semantic_search": True, "limit": 3},
        conversation_id=conversation_id,
    )
    assert (
        len(resp2.get("results", [])) > 0
    ), "No results from agent in second turn of conversation"


def test_complex_filters_and_fulltext(client, test_collection):
    # collection_id, doc_ids = _setup_collection_with_documents(client)

    # rating > 5
    me = client.users.me()
    print("me = ", me)
    # include  owner id and collection ids to make robust against other database interactions from other users
    filters = {
        "rating": {"$gt": 5},
        "owner_id": {"$eq": client.users.me()["results"]["id"]},
        "collection_ids": {
            "$overlap": [str(test_collection["collection_id"])]
        },
    }
    resp = client.retrieval.search(
        query="a",
        search_mode=SearchMode.custom,
        search_settings={"use_semantic_search": True, "filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    print("results = ", results)
    assert (
        len(results) == 2
    ), f"Expected 2 docs with rating > 5, got {len(results)}"

    # category in [ancient, modern]
    filters = {
        "metadata.category": {"$in": ["ancient", "modern"]},
        "owner_id": {"$eq": client.users.me()["results"]["id"]},
        "collection_ids": {
            "$overlap": [str(test_collection["collection_id"])]
        },
    }

    resp = client.retrieval.search(
        query="b",
        search_mode=SearchMode.custom,
        search_settings={"use_semantic_search": True, "filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    print("Filters being applied:", filters)
    print("Current user ID:", client.users.me()["results"]["id"])
    print("Test collection ID:", test_collection["collection_id"])
    print("All available documents:", client.documents.list()["results"])
    assert len(results) == 4, f"Expected all 4 docs, got {len(results)}"

    # rating > 5 AND category=modern
    filters = {
        "$and": [
            {"metadata.rating": {"$gt": 5}},
            {"metadata.category": {"$eq": "modern"}},
            {"owner_id": {"$eq": client.users.me()["results"]["id"]}},
            {
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                }
            },
        ],
    }
    resp = client.retrieval.search(
        query="d",
        search_mode=SearchMode.custom,
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    assert (
        len(results) == 2
    ), f"Expected 2 modern docs with rating>5, got {len(results)}"

    # full-text search: "unique_philosopher"
    resp = client.retrieval.search(
        query="unique_philosopher",
        search_mode=SearchMode.custom,
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "filters": {
                "owner_id": {"$eq": client.users.me()["results"]["id"]},
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                },
            },
        },
    )["results"]
    results = resp["chunk_search_results"]
    assert (
        len(results) == 1
    ), f"Expected 1 doc for unique_philosopher, got {len(results)}"


def test_complex_nested_filters(client, test_collection):
    # Setup docs
    # _setup_collection_with_documents(client)

    # ((category=ancient OR rating<5) AND tags contains 'philosophy')
    filters = {
        "$and": [
            {
                "$or": [
                    {"metadata.category": {"$eq": "ancient"}},
                    {"metadata.rating": {"$lt": 5}},
                ]
            },
            {"metadata.tags": {"$contains": ["philosophy"]}},
            {"owner_id": {"$eq": client.users.me()["results"]["id"]}},
            {
                "collection_ids": {
                    "$overlap": [str(test_collection["collection_id"])]
                }
            },
        ],
    }

    resp = client.retrieval.search(
        query="complex",
        search_mode="custom",
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    print("results = ", results)
    assert len(results) == 2, f"Expected 2 docs, got {len(results)}"


def test_invalid_operator(client):
    filters = {"metadata.category": {"$like": "%ancient%"}}
    with pytest.raises(R2RException):
        client.retrieval.search(
            query="abc",
            search_mode="custom",
            search_settings={"filters": filters},
        )


def test_filters_no_match(client):
    filters = {"metadata.category": {"$in": ["nonexistent"]}}
    resp = client.retrieval.search(
        query="noresults",
        search_mode="custom",
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    assert len(results) == 0, f"Expected 0 docs, got {len(results)}"


def test_pagination_extremes(client):
    chunk_list = client.chunks.list()
    total_entries = chunk_list["total_entries"]

    offset = total_entries + 100
    resp = client.retrieval.search(
        query="Aristotle",
        search_mode="basic",
        search_settings={"limit": 10, "offset": offset},
    )["results"]
    results = resp["chunk_search_results"]
    print("results = ", results)
    assert (
        len(results) == 0
    ), f"Expected no results at large offset, got {len(results)}"


def test_full_text_stopwords(client):
    resp = client.retrieval.search(
        query="the",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 5,
        },
    )
    assert "results" in resp, "No results field in stopword query response"


def test_full_text_non_ascii(client):
    resp = client.retrieval.search(
        query="Aristotélēs",
        search_mode="custom",
        search_settings={
            "use_fulltext_search": True,
            "use_semantic_search": False,
            "limit": 3,
        },
    )
    assert "results" in resp, "No results field in non-ASCII query response"


def test_missing_fields(client):
    filters = {"metadata.someNonExistentField": {"$eq": "anything"}}
    resp = client.retrieval.search(
        query="missingfield",
        search_mode="custom",
        search_settings={"filters": filters},
    )["results"]
    results = resp["chunk_search_results"]
    assert (
        len(results) == 0
    ), f"Expected 0 docs for a non-existent field, got {len(results)}"


def test_rag_with_large_context(client):
    resp = client.retrieval.rag(
        query="Explain the contributions of Kant in detail",
        rag_generation_config={"stream": False, "max_tokens": 200},
        search_settings={"use_semantic_search": True, "limit": 10},
    )
    results = resp.get("results", {})
    assert "completion" in results, "RAG large context missing 'completion'"
    completion = results["completion"]["choices"][0]["message"]["content"]
    assert len(completion) > 0, "RAG large context returned empty answer"


def test_agent_long_conversation(client):
    conversation = client.conversations.create()["results"]
    conversation_id = conversation["id"]

    msg1 = Message(role="user", content="What were Aristotle's main ideas?")
    resp1 = client.retrieval.agent(
        message=msg1,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert "results" in resp1, "No results in first turn of conversation"

    msg2 = Message(
        role="user", content="How did these ideas influence modern philosophy?"
    )
    resp2 = client.retrieval.agent(
        message=msg2,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert "results" in resp2, "No results in second turn of conversation"

    msg3 = Message(role="user", content="Now tell me about Descartes.")
    resp3 = client.retrieval.agent(
        message=msg3,
        rag_generation_config={"stream": False, "max_tokens": 100},
        search_settings={"use_semantic_search": True, "limit": 5},
        conversation_id=conversation_id,
    )
    assert "results" in resp3, "No results in third turn of conversation"


def test_filter_by_document_type(client):
    random_suffix = str(uuid.uuid4())
    client.documents.create(
        chunks=[
            f"a {random_suffix}",
            f"b {random_suffix}",
            f"c {random_suffix}",
        ]
    )
    filters = {"document_type": {"$eq": "txt"}}
    resp = client.retrieval.search(
        query="a", search_settings={"filters": filters}
    )["results"]
    results = resp["chunk_search_results"]
    # Depending on your environment, if no txt documents exist this might fail.
    # Adjust accordingly to ensure there's a txt doc available or mock if needed.
    assert len(results) > 0, "No results found for filter by document type"
