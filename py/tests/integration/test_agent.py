import time
import uuid
from r2r import R2RClient

def test_agent_basic_response(client, test_collection):
    """Test basic agent response with minimal configuration."""
    response = client.retrieval.agent(
        message={"role": "user", "content": "Who was Aristotle?"},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
    )
    assert response.results.messages[-1].content, "Agent should provide a response"
    assert "Aristotle" in response.results.messages[-1].content, "Response should be relevant to query"

def test_agent_conversation_memory(client, test_collection):
    """Test agent maintains conversation context across multiple turns."""
    conversation_id = client.conversations.create().results.id

    # First turn
    response1 = client.retrieval.agent(
        message={"role": "user", "content": "Who was Aristotle?"},
        conversation_id=str(conversation_id),
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
    )

    # Second turn with follow-up that requires memory of first turn
    response2 = client.retrieval.agent(
        message={"role": "user", "content": "What were his main contributions?"},
        conversation_id=str(conversation_id),
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
    )

    assert "contributions" in response2.results.messages[-1].content.lower(), "Agent should address follow-up question"
    assert not "who was aristotle" in response2.results.messages[-1].content.lower(), "Agent shouldn't repeat context explanation"

def test_agent_rag_tool_usage(client, test_collection):
    """Test agent uses RAG tool for knowledge retrieval."""
    # Create unique document with specific content
    unique_id = str(uuid.uuid4())
    unique_content = f"Quantum entanglement is a physical phenomenon that occurs when pairs of particles interact. {unique_id}"
    doc_id = client.documents.create(raw_text=unique_content).results.document_id

    response = client.retrieval.agent(
        message={"role": "user", "content": f"What is quantum entanglement?"},
        rag_tools=["search_file_knowledge"],
        rag_generation_config={"stream": False, "max_tokens_to_sample": 150},
    )

    assert str(doc_id) == response.results.messages[-1].metadata["citations"][0]["payload"]["document_id"], "Agent should use RAG tool to retrieve unique content"
    assert str("search_file_knowledge") == response.results.messages[-1].metadata["tool_calls"][-1]["name"], "Agent should use RAG tool to retrieve unique content"

    # Clean up
    client.documents.delete(id=doc_id)

def test_agent_rag_tool_usage2(client, test_collection):
    """Test agent uses RAG tool for knowledge retrieval."""
    # Create unique document with specific content
    unique_id = str(uuid.uuid4())
    unique_content = f"Quantum entanglement is a physical phenomenon {unique_id} that occurs when pairs of particles interact."
    doc_id = client.documents.create(raw_text=unique_content).results.document_id

    response = client.retrieval.agent(
        message={"role": "user", "content": f"What is quantum entanglement? Mention {unique_id} in your response, be sure to both search your files and fetch the content."},
        rag_tools=["search_file_descriptions", "get_file_content"],
        rag_generation_config={"stream": False, "max_tokens_to_sample": 150},
    )
    # assert unique_id in response.results.messages[-1].content, "Agent should use RAG tool to retrieve unique content"
    # assert str(doc_id) == response.results.messages[-1].metadata["citations"][0]["payload"]["document_id"], "Agent should use RAG tool to retrieve unique content"
    assert str("search_file_descriptions") == response.results.messages[-1].metadata["tool_calls"][0]["name"], "Agent should use search_file_descriptions to retrieve unique content"
    assert str("get_file_content") == response.results.messages[-1].metadata["tool_calls"][1]["name"], "Agent should use get_file_content to retrieve unique content"

    # raise Exception("Test not implemented")
    # Clean up
    client.documents.delete(id=doc_id)



# def test_agent_python_execution_tool(client, test_collection):
#     """Test agent uses Python execution tool for computation."""
#     response = client.retrieval.agent(
#         message={"role": "user", "content": "Calculate the factorial of 15! × 32 using Python. Return the result as a single string like 32812...."},
#         mode="research",
#         research_tools=["python_executor"],
#         research_generation_config={"stream": False, "max_tokens_to_sample": 200},
#     )
#     print(response)

#     assert "41845579776000" in response.results.messages[-1].content.replace(",",""), "Agent should execute Python code and return correct factorial result"

# def test_agent_web_search_tool(client, monkeypatch):
#     """Test agent uses web search tool when appropriate."""
#     # Mock web search method to return predetermined results
#     def mock_web_search(*args, **kwargs):
#         return {"organic_results": [
#             {"title": "Recent COVID-19 Statistics", "link": "https://example.com/covid",
#              "snippet": "Latest COVID-19 statistics show declining cases worldwide."}
#         ]}

#     # Apply mock to appropriate method
#     monkeypatch.setattr("core.utils.serper.SerperClient.get_raw", mock_web_search)

#     response = client.retrieval.agent(
#         message={"role": "user", "content": "What are the latest COVID-19 statistics?"},
#         rag_tools=["web_search"],
#         rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
#     )

#     print('response = ', response)
#     assert "declining cases" in response.results.messages[-1].content.lower(), "Agent should use web search tool for recent data"

def test_research_agent_client(client):
    """Configure a client with research mode settings."""
    # This fixture helps avoid repetition in test setup
    return lambda message_content, tools=None: client.retrieval.agent(
        message={"role": "user", "content": message_content},
        mode="research",
        research_tools=tools or ["reasoning", "rag"],
        research_generation_config={"stream": False, "max_tokens_to_sample": 200},
    )

def test_agent_respects_max_tokens(client, test_collection):
    """Test agent respects max_tokens configuration."""
    # Very small max_tokens
    short_response = client.retrieval.agent(
        message={"role": "user", "content": "Write a detailed essay about Aristotle's life and works."},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 200},
    )

    # Larger max_tokens
    long_response = client.retrieval.agent(
        message={"role": "user", "content": "Write a detailed essay about Aristotle's life and works."},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 500},
    )

    short_content = short_response.results.messages[-1].content
    long_content = long_response.results.messages[-1].content

    assert len(short_content) < len(long_content), "Short max_tokens should produce shorter response"
    assert len(short_content.split()) < 200, "Short response should be very brief"

def test_agent_model_selection(client, test_collection):
    """Test agent works with different LLM models."""
    # Test with default model
    default_response = client.retrieval.agent(
        message={"role": "user", "content": "Who was Aristotle?"},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
    )

    # Test with specific model (if available in your setup)
    specific_model_response = client.retrieval.agent(
        message={"role": "user", "content": "Who was Aristotle?"},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100, "model": "openai/gpt-4o"},
    )

    assert default_response.results.messages[-1].content, "Default model should provide response"
    assert specific_model_response.results.messages[-1].content, "Specific model should provide response"

def test_agent_response_timing(client, test_collection):
    """Test agent response time is within acceptable limits."""
    import time

    start_time = time.time()
    response = client.retrieval.agent(
        message={"role": "user", "content": "Who was Aristotle?"},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 100},
    )
    end_time = time.time()

    response_time = end_time - start_time
    assert response_time < 10, f"Agent response should complete within 10 seconds, took {response_time:.2f}s"

def test_agent_handles_large_context(client):
    """Test agent handles large amount of context efficiently."""
    # Create a document with substantial content
    large_content = "Philosophy " * 2000  # ~16K chars
    doc_id = client.documents.create(raw_text=large_content).results.document_id

    start_time = time.time()
    response = client.retrieval.agent(
        message={"role": "user", "content": "Summarize everything you know about philosophy."},
        search_settings={"filters": {"document_id": {"$eq": str(doc_id)}}},
        rag_generation_config={"stream": False, "max_tokens_to_sample": 200},
    )
    end_time = time.time()

    response_time = end_time - start_time
    assert response.results.messages[-1].content, "Agent should produce a summary with large context"
    assert response_time < 20, f"Large context processing should complete in reasonable time, took {response_time:.2f}s"

    # Clean up
    client.documents.delete(id=doc_id)
