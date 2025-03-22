"""
Unit tests for the core R2RStreamingAgent functionality.

These tests focus on the core functionality of the agent, separate from
citation-specific behavior which is tested in test_agent_citations.py.
"""

import pytest
import asyncio
import json
import re
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, List, Tuple, Any, AsyncGenerator

import pytest_asyncio

from core.base import Message, LLMChatCompletion, LLMChatCompletionChunk, GenerationConfig
from core.utils import CitationTracker, SearchResultsCollector, SSEFormatter
from core.agent.base import R2RStreamingAgent

# Import mock classes from conftest
from conftest import (
    MockDatabaseProvider,
    MockLLMProvider,
    MockR2RStreamingAgent,
    MockSearchResultsCollector,
    collect_stream_output
)


@pytest.mark.asyncio
async def test_streaming_agent_functionality():
    """Test basic functionality of the streaming agent."""
    # Create mock config
    config = MagicMock()
    config.stream = True

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a test response",
        citations=[]
    )
    db_provider = MockDatabaseProvider()

    # Create mock search results collector
    search_results_collector = MockSearchResultsCollector({})

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Set the search results collector
    agent.search_results_collector = search_results_collector

    # Test a simple query
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Verify response
    message_events = [line for line in output if 'event: message' in line]
    assert len(message_events) > 0, "Message event should be emitted"

    # Verify final answer
    final_answer_events = [line for line in output if 'event: agent.final_answer' in line]
    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    # Verify done event
    done_events = [line for line in output if 'event: done' in line]
    assert len(done_events) > 0, "Done event should be emitted"


@pytest.mark.asyncio
async def test_agent_handles_multiple_messages():
    """Test agent handles conversation with multiple messages."""
    # Create mock config
    config = MagicMock()
    config.stream = True

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a response to multiple messages",
        citations=[]
    )
    db_provider = MockDatabaseProvider()

    # Create mock search results collector
    search_results = {
        "abc1234": {
            "document_id": "doc_abc1234",
            "text": "This is document text for abc1234",
            "metadata": {"source": "source_abc1234"}
        },
        "def5678": {
            "document_id": "doc_def5678",
            "text": "This is document text for def5678",
            "metadata": {"source": "source_def5678"}
        }
    }
    search_results_collector = MockSearchResultsCollector(search_results)

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Set the search results collector
    agent.search_results_collector = search_results_collector

    # Test with multiple messages
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="First question"),
        Message(role="assistant", content="First answer"),
        Message(role="user", content="Follow-up question")
    ]

    # Run the agent
    stream = agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Verify response
    message_events = [line for line in output if 'event: message' in line]
    assert len(message_events) > 0, "Message event should be emitted"

    # After running, check that conversation has the new assistant response
    # Note: MockR2RStreamingAgent._setup adds a default system message
    # and then our messages are added, plus the agent's response
    assert len(agent.conversation.messages) == 6, "Conversation should have correct number of messages"

    # The last message should be the assistant's response
    assert agent.conversation.messages[-1].role == "assistant", "Last message should be from assistant"

    # We should have two system messages (default + our custom one)
    system_messages = [m for m in agent.conversation.messages if m.role == "system"]
    assert len(system_messages) == 2, "Should have two system messages"


@pytest.mark.asyncio
async def test_agent_event_format():
    """Test the format of events emitted by the agent."""
    # Create mock config
    config = MagicMock()
    config.stream = True

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a test of event formatting",
        citations=[]
    )
    db_provider = MockDatabaseProvider()

    # Create mock search results collector
    search_results_collector = MockSearchResultsCollector({})

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Set the search results collector
    agent.search_results_collector = search_results_collector

    # Test a simple query
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Check message event format
    message_events = [line for line in output if 'event: message' in line]
    assert len(message_events) > 0, "Message event should be emitted"

    data_part = message_events[0].split('data: ')[1] if 'data: ' in message_events[0] else ""
    try:
        data = json.loads(data_part)
        assert "content" in data, "Message event should include content"
    except json.JSONDecodeError:
        assert False, "Message event data should be valid JSON"

    # Check final answer event format
    final_answer_events = [line for line in output if 'event: agent.final_answer' in line]
    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    data_part = final_answer_events[0].split('data: ')[1] if 'data: ' in final_answer_events[0] else ""
    try:
        data = json.loads(data_part)
        assert "id" in data, "Final answer event should include ID"
        assert "object" in data, "Final answer event should include object type"
        assert "generated_answer" in data, "Final answer event should include generated answer"
    except json.JSONDecodeError:
        assert False, "Final answer event data should be valid JSON"


@pytest.mark.asyncio
async def test_final_answer_event_format():
    """Test that the final answer event has the expected format and content."""
    # Create mock config
    config = MagicMock()
    config.stream = True

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a test final answer",
        citations=[]
    )
    db_provider = MockDatabaseProvider()

    # Create mock search results collector
    search_results_collector = MockSearchResultsCollector({})

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Set the search results collector
    agent.search_results_collector = search_results_collector

    # Test a simple query
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Extract and verify final answer event
    final_answer_events = [line for line in output if 'event: agent.final_answer' in line]
    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    data_part = final_answer_events[0].split('data: ')[1] if 'data: ' in final_answer_events[0] else ""
    try:
        data = json.loads(data_part)
        assert data["id"] == "msg_final", "Final answer ID should be msg_final"
        assert data["object"] == "agent.final_answer", "Final answer object should be agent.final_answer"
        assert "generated_answer" in data, "Final answer should include generated_answer"
        assert "citations" in data, "Final answer should include citations field"
    except json.JSONDecodeError:
        assert False, "Final answer event data should be valid JSON"


@pytest.mark.asyncio
async def test_conversation_message_format():
    """Test that the conversation includes properly formatted assistant messages."""
    # Create mock config
    config = MagicMock()
    config.stream = True

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a test message",
        citations=[]
    )
    db_provider = MockDatabaseProvider()

    # Create mock search results collector
    search_results = {
        "abc1234": {
            "document_id": "doc_abc1234",
            "text": "This is document text for abc1234",
            "metadata": {"source": "source_abc1234"}
        },
        "def5678": {
            "document_id": "doc_def5678",
            "text": "This is document text for def5678",
            "metadata": {"source": "source_def5678"}
        }
    }
    search_results_collector = MockSearchResultsCollector(search_results)

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Set the search results collector
    agent.search_results_collector = search_results_collector

    # Test a simple query
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = agent.arun(messages=messages)
    await collect_stream_output(stream)

    # Get the last message from the conversation
    last_message = agent.conversation.messages[-1]

    # Verify message format - note that MockR2RStreamingAgent uses a hardcoded response
    assert last_message.role == "assistant", "Last message should be from assistant"
    assert "This is a test response with citations" in last_message.content, "Message content should include response"
    assert "metadata" in last_message.dict(), "Message should include metadata"
    assert "citations" in last_message.metadata, "Message metadata should include citations"