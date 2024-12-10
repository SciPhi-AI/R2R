import argparse
import sys
import time
import uuid

from r2r import GenerationConfig, Message, R2RClient, R2RException


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
    assert_http_error(
        "content" in resp["results"], "No 'content' in completion result"
    )
    print("Completion test passed")
    print("~" * 100)


def test_embedding():
    print("Testing: Embedding")
    text = "Who is Aristotle?"
    resp = client.retrieval.embedding(text=text)
    # Expect some embedding vector in result
    assert_http_error(
        "results" in resp, "Embedding response missing 'results'"
    )
    emb = resp["results"].get("embedding")
    assert_http_error(
        emb is not None and isinstance(emb, list),
        "No embedding vector returned",
    )
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
