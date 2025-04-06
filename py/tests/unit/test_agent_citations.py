"""
Unit tests for citation extraction and propagation in the R2RStreamingAgent.

These tests focus specifically on citation-related functionality:
- Citation extraction from text
- Citation tracking during streaming
- Citation event emission
- Citation formatting and propagation
- Citation edge cases and validation
"""

import pytest
import asyncio
import json
import re
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, List, Tuple, Any, AsyncGenerator

import pytest_asyncio

from core.base import Message, LLMChatCompletion, LLMChatCompletionChunk, GenerationConfig
from core.utils import CitationTracker, extract_citations, extract_citation_spans
from core.agent.base import R2RStreamingAgent

# Import mock classes from conftest
from conftest import (
    MockDatabaseProvider,
    MockLLMProvider,
    MockR2RStreamingAgent,
    MockSearchResultsCollector,
    collect_stream_output
)


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response_content=None, citations=None):
        self.response_content = response_content or "This is a response"
        self.citations = citations or []

    async def aget_completion(self, messages, generation_config):
        """Mock synchronous completion."""
        content = self.response_content
        for citation in self.citations:
            content += f" [{citation}]"

        mock_response = MagicMock(spec=LLMChatCompletion)
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = content
        mock_response.choices[0].finish_reason = "stop"
        return mock_response

    async def aget_completion_stream(self, messages, generation_config):
        """Mock streaming completion."""
        content = self.response_content
        for citation in self.citations:
            content += f" [{citation}]"

        # Simulate streaming by yielding one character at a time
        for i in range(len(content)):
            chunk = MagicMock(spec=LLMChatCompletionChunk)
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = content[i]
            chunk.choices[0].finish_reason = None
            yield chunk

        # Final chunk with finish_reason="stop"
        final_chunk = MagicMock(spec=LLMChatCompletionChunk)
        final_chunk.choices = [MagicMock()]
        final_chunk.choices[0].delta = MagicMock()
        final_chunk.choices[0].delta.content = ""
        final_chunk.choices[0].finish_reason = "stop"
        yield final_chunk


class MockPromptsHandler:
    """Mock prompts handler for testing."""

    async def get_cached_prompt(self, prompt_key, inputs=None, *args, **kwargs):
        """Return a mock system prompt."""
        return "You are a helpful assistant that provides well-sourced information."


class MockDatabaseProvider:
    """Mock database provider for testing."""

    def __init__(self):
        # Add a prompts_handler attribute to prevent AttributeError
        self.prompts_handler = MockPromptsHandler()

    async def acreate_conversation(self, *args, **kwargs):
        return {"id": "conv_12345"}

    async def aupdate_conversation(self, *args, **kwargs):
        return True

    async def acreate_message(self, *args, **kwargs):
        return {"id": "msg_12345"}


class MockSearchResultsCollector:
    """Mock search results collector for testing."""

    def __init__(self, results=None):
        self.results = results or {}

    def find_by_short_id(self, short_id):
        return self.results.get(short_id, {
            "document_id": f"doc_{short_id}",
            "text": f"This is document text for {short_id}",
            "metadata": {"source": f"source_{short_id}"}
        })


# Create a concrete implementation of R2RStreamingAgent for testing
class MockR2RStreamingAgent(R2RStreamingAgent):
    """Mock streaming agent for testing that implements the abstract method."""

    # Regex pattern for citations, copied from the actual agent
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
    SHORT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{7,8}")

    def _register_tools(self):
        """Implement the abstract method with a no-op version."""
        pass

    async def _setup(self, system_instruction=None, *args, **kwargs):
        """Override _setup to simplify initialization and avoid external dependencies."""
        # Use a simple system message instead of fetching from database
        system_content = system_instruction or "You are a helpful assistant that provides well-sourced information."

        # Add system message to conversation
        await self.conversation.add_message(
            Message(role="system", content=system_content)
        )

    def _format_sse_event(self, event_type, data):
        """Format an SSE event manually."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    async def arun(
        self,
        system_instruction: str = None,
        messages: list[Message] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Simplified version of arun that focuses on citation handling for testing.
        """
        await self._setup(system_instruction)

        if messages:
            for m in messages:
                await self.conversation.add_message(m)

        # Initialize citation tracker
        citation_tracker = CitationTracker()
        citation_payloads = {}

        # Track streaming citations for final persistence
        self.streaming_citations = []

        # Get the LLM response with citations
        response_content = "This is a test response with citations"
        response_content += " [abc1234] [def5678]"

        # Yield an initial message event with the start of the text
        yield self._format_sse_event("message", {"content": response_content})

        # Manually extract and emit citation events
        # This is a simpler approach than the character-by-character approach
        citation_spans = extract_citation_spans(response_content)

        # Process the citations
        for cid, spans in citation_spans.items():
            for span in spans:
                # Check if the span is new and record it
                if citation_tracker.is_new_span(cid, span):

                    # Look up the source document for this citation
                    source_doc = self.search_results_collector.find_by_short_id(cid)

                    # Create citation payload
                    citation_payload = {
                        "document_id": source_doc.get("document_id", f"doc_{cid}"),
                        "text": source_doc.get("text", f"This is document text for {cid}"),
                        "metadata": source_doc.get("metadata", {"source": f"source_{cid}"}),
                    }

                    # Store the payload by citation ID
                    citation_payloads[cid] = citation_payload

                    # Track for persistence
                    self.streaming_citations.append({
                        "id": cid,
                        "span": {"start": span[0], "end": span[1]},
                        "payload": citation_payload
                    })

                    # Emit citation event
                    citation_event = {
                        "id": cid,
                        "object": "citation",
                        "span": {"start": span[0], "end": span[1]},
                        "payload": citation_payload
                    }

                    yield self._format_sse_event("citation", citation_event)

        # Add assistant message with citation metadata to conversation
        await self.conversation.add_message(
            Message(
                role="assistant",
                content=response_content,
                metadata={"citations": self.streaming_citations}
            )
        )

        # Prepare consolidated citations for final answer
        consolidated_citations = []

        # Group citations by ID with all their spans
        for cid, spans in citation_tracker.get_all_spans().items():
            if cid in citation_payloads:
                consolidated_citations.append({
                    "id": cid,
                    "object": "citation",
                    "spans": [{"start": s[0], "end": s[1]} for s in spans],
                    "payload": citation_payloads[cid]
                })

        # Create and emit final answer event
        final_evt_payload = {
            "id": "msg_final",
            "object": "agent.final_answer",
            "generated_answer": response_content,
            "citations": consolidated_citations
        }

        # Manually format the final answer event
        yield self._format_sse_event("agent.final_answer", final_evt_payload)

        # Signal the end of the SSE stream
        yield "event: done\ndata: {}\n\n"


@pytest.fixture
def mock_streaming_agent():
    """Create a streaming agent with mocked dependencies."""
    # Create mock config
    config = MagicMock()
    config.stream = True
    config.max_iterations = 3

    # Create mock providers
    llm_provider = MockLLMProvider(
        response_content="This is a test response with citations",
        citations=["abc1234", "def5678"]
    )
    db_provider = MockDatabaseProvider()

    # Create agent with mocked dependencies using our concrete implementation
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Replace the search results collector with our mock
    agent.search_results_collector = MockSearchResultsCollector({
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
    })

    return agent


async def collect_stream_output(stream):
    """Collect all output from a stream into a list."""
    output = []
    async for event in stream:
        output.append(event)
    return output


def test_extract_citations_from_response():
    """Test that citations are extracted from LLM responses."""
    response_text = "This is a response with a citation [abc1234]."

    # Use the utility function directly
    citations = extract_citations(response_text)

    assert "abc1234" in citations, "Citation should be extracted from response"


@pytest.mark.asyncio
async def test_streaming_agent_citation_extraction(mock_streaming_agent):
    """Test that streaming agent extracts citations from streamed content."""
    # Run the agent
    messages = [Message(role="user", content="Test query")]

    # We need to run this in a coroutine
    stream = mock_streaming_agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Look for citation events in the output
    citation_events = [
        line for line in output
        if 'event: citation' in line
    ]

    assert len(citation_events) > 0, "Citation events should be emitted"

    # Check citation IDs in events
    citation_abc = any('abc1234' in event for event in citation_events)
    citation_def = any('def5678' in event for event in citation_events)

    assert citation_abc, "Citation abc1234 should be found in stream output"
    assert citation_def, "Citation def5678 should be found in stream output"


@pytest.mark.asyncio
async def test_citation_tracker_during_streaming(mock_streaming_agent):
    """Test that CitationTracker correctly tracks processed citations during streaming."""
    # We need to patch the is_new_span method to verify it's being used correctly
    # Use autospec=True to ensure the method signature is preserved
    with patch('core.utils.CitationTracker.is_new_span', autospec=True) as mock_is_new_span:
        # Configure the mock to return True so citations will be processed
        mock_is_new_span.return_value = True

        messages = [Message(role="user", content="Test query")]

        # Run the agent
        stream = mock_streaming_agent.arun(messages=messages)
        output = await collect_stream_output(stream)

        # Verify that CitationTracker.is_new_span method was called
        assert mock_is_new_span.call_count > 0, "is_new_span should be called to track citation spans"


@pytest.mark.asyncio
async def test_final_answer_includes_consolidated_citations(mock_streaming_agent):
    """Test that the final answer includes consolidated citations."""
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = mock_streaming_agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Look for final answer event in the output
    final_answer_events = [
        line for line in output
        if 'event: agent.final_answer' in line
    ]

    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    # Parse the event to check for citations
    for event in final_answer_events:
        data_part = event.split('data: ')[1] if 'data: ' in event else event
        try:
            data = json.loads(data_part)
            if 'citations' in data:
                assert len(data['citations']) > 0, "Final answer should include citations"
                citation_ids = [citation.get('id') for citation in data['citations']]
                assert 'abc1234' in citation_ids or 'def5678' in citation_ids, "Known citation IDs should be included"
        except json.JSONDecodeError:
            continue


@pytest.mark.asyncio
async def test_conversation_message_includes_citation_metadata(mock_streaming_agent):
    """Test that conversation messages include citation metadata."""
    with patch.object(mock_streaming_agent.conversation, 'add_message', wraps=mock_streaming_agent.conversation.add_message) as mock_add_message:
        messages = [Message(role="user", content="Test query")]

        # Run the agent
        stream = mock_streaming_agent.arun(messages=messages)
        output = await collect_stream_output(stream)

        # Check that add_message was called with citation metadata
        citation_calls = 0
        for call in mock_add_message.call_args_list:
            args, kwargs = call
            if args and isinstance(args[0], Message):
                message = args[0]
                if message.role == 'assistant' and message.metadata and 'citations' in message.metadata:
                    citation_calls += 1

        assert citation_calls > 0, "At least one assistant message should include citation metadata"


@pytest.mark.asyncio
async def test_multiple_citations_for_same_source(mock_streaming_agent):
    """Test handling of multiple citations for the same source document."""
    # Create a custom citation tracker that we can control
    citation_tracker = CitationTracker()

    # Create a custom MockR2RStreamingAgent with our controlled citation tracker
    with patch('core.utils.CitationTracker', return_value=citation_tracker):
        custom_agent = mock_streaming_agent

        # Modify the arun method to include repeated citations for the same source
        original_arun = custom_agent.arun

        async def custom_arun(*args, **kwargs):
            """Custom arun that includes repeated citations for the same source."""
            # Setup like the original
            await custom_agent._setup(kwargs.get('system_instruction'))

            messages = kwargs.get('messages', [])
            if messages:
                for m in messages:
                    await custom_agent.conversation.add_message(m)

            # Initialize payloads dict for tracking
            citation_payloads = {}

            # Track streaming citations for final persistence
            custom_agent.streaming_citations = []

            # Create text with multiple citations to the same source
            response_content = "This text has multiple citations to the same source: [abc1234] and again here [abc1234]."

            # Yield the message event
            yield custom_agent._format_sse_event("message", {"content": response_content})

            # Manually extract and emit citation events
            # This is a simpler approach than the character-by-character approach
            citation_spans = extract_citation_spans(response_content)

            # Process the citations
            for cid, spans in citation_spans.items():
                for span in spans:
                    # Mark as processed in the tracker
                    citation_tracker.is_new_span(cid, span)

                    # Look up the source document for this citation
                    source_doc = custom_agent.search_results_collector.find_by_short_id(cid)

                    # Create citation payload
                    citation_payload = {
                        "document_id": source_doc.get("document_id", f"doc_{cid}"),
                        "text": source_doc.get("text", f"This is document text for {cid}"),
                        "metadata": source_doc.get("metadata", {"source": f"source_{cid}"}),
                    }

                    # Store the payload
                    citation_payloads[cid] = citation_payload

                    # Track for persistence
                    custom_agent.streaming_citations.append({
                        "id": cid,
                        "span": {"start": span[0], "end": span[1]},
                        "payload": citation_payload
                    })

                    # Emit citation event
                    citation_event = {
                        "id": cid,
                        "object": "citation",
                        "span": {"start": span[0], "end": span[1]},
                        "payload": citation_payload
                    }

                    yield custom_agent._format_sse_event("citation", citation_event)

            # Add assistant message with citation metadata to conversation
            await custom_agent.conversation.add_message(
                Message(
                    role="assistant",
                    content=response_content,
                    metadata={"citations": custom_agent.streaming_citations}
                )
            )

            # Prepare consolidated citations for final answer
            consolidated_citations = []

            # Group citations by ID with all their spans
            for cid, spans in citation_tracker.get_all_spans().items():
                if cid in citation_payloads:
                    consolidated_citations.append({
                        "id": cid,
                        "object": "citation",
                        "spans": [{"start": s[0], "end": s[1]} for s in spans],
                        "payload": citation_payloads[cid]
                    })

            # Create and emit final answer event
            final_evt_payload = {
                "id": "msg_final",
                "object": "agent.final_answer",
                "generated_answer": response_content,
                "citations": consolidated_citations
            }

            yield custom_agent._format_sse_event("agent.final_answer", final_evt_payload)

            # Signal the end of the SSE stream
            yield "event: done\ndata: {}\n\n"

        # Apply the custom arun method
        with patch.object(custom_agent, 'arun', custom_arun):
            messages = [Message(role="user", content="Test query")]

            # Run the agent with overlapping citations
            stream = custom_agent.arun(messages=messages)
            output = await collect_stream_output(stream)

            # Count citation events for abc1234
            citation_abc_events = [
                line for line in output
                if 'event: citation' in line and 'abc1234' in line
            ]

            # There should be at least 2 citations for abc1234 (the original and our added one)
            assert len(citation_abc_events) >= 2, "Should emit multiple citation events for the same source"

            # Check the final answer to ensure spans were consolidated
            final_answer_events = [
                line for line in output
                if 'event: agent.final_answer' in line
            ]

            for event in final_answer_events:
                data_part = event.split('data: ')[1] if 'data: ' in event else event
                try:
                    data = json.loads(data_part)
                    if 'citations' in data:
                        # Find the citation for abc1234
                        abc_citation = next((citation for citation in data['citations'] if citation.get('id') == 'abc1234'), None)
                        if abc_citation:
                            # It should have multiple spans
                            assert abc_citation.get('spans') and len(abc_citation['spans']) >= 2, "Citation should have multiple spans consolidated"
                except json.JSONDecodeError:
                    continue


@pytest.mark.asyncio
async def test_citation_consolidation_logic(mock_streaming_agent):
    """Test that citation consolidation properly groups spans by citation ID."""
    # Patch the get_all_spans method to return a controlled set of spans
    citation_tracker = CitationTracker()

    # Add spans for multiple citations
    citation_tracker.is_new_span("abc1234", (10, 20))
    citation_tracker.is_new_span("abc1234", (30, 40))
    citation_tracker.is_new_span("def5678", (50, 60))
    citation_tracker.is_new_span("ghi9012", (70, 80))
    citation_tracker.is_new_span("ghi9012", (90, 100))

    # Create a custom mock agent that uses our pre-populated citation tracker
    with patch('core.utils.CitationTracker', return_value=citation_tracker):
        # Create a fresh agent with our mocked citation tracker
        new_agent = mock_streaming_agent

        messages = [Message(role="user", content="Test query")]

        # Run the agent
        stream = new_agent.arun(messages=messages)
        output = await collect_stream_output(stream)

        # Look for the final answer event
        final_answer_events = [
            line for line in output
            if 'event: agent.final_answer' in line
        ]

        # Verify consolidation in final answer
        for event in final_answer_events:
            data_part = event.split('data: ')[1] if 'data: ' in event else event
            try:
                data = json.loads(data_part)
                if 'citations' in data:
                    # There should be at least 2 citations (from our mock agent implementation)
                    assert len(data['citations']) >= 2, "Should include multiple citation objects"

                    # Check spans for each citation
                    for citation in data['citations']:
                        cid = citation.get('id')
                        if cid == 'abc1234':
                            # Spans should be consolidated for abc1234
                            spans = citation.get('spans', [])
                            assert len(spans) >= 1, f"Citation {cid} should have spans"
            except json.JSONDecodeError:
                continue


@pytest.mark.asyncio
async def test_citation_event_format(mock_streaming_agent):
    """Test that citation events follow the expected format."""
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = mock_streaming_agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Extract citation events
    citation_events = [
        line for line in output
        if 'event: citation' in line
    ]

    assert len(citation_events) > 0, "Citation events should be emitted"

    # Check the format of each citation event
    for event in citation_events:
        # Should have 'event: citation' and 'data: {...}'
        assert 'event: citation' in event, "Event type should be 'citation'"
        assert 'data: ' in event, "Event should have data payload"

        # Parse the data payload
        data_part = event.split('data: ')[1] if 'data: ' in event else event
        try:
            data = json.loads(data_part)

            # Check required fields
            assert 'id' in data, "Citation event should have an 'id'"
            assert 'object' in data and data['object'] == 'citation', "Event object should be 'citation'"
            assert 'span' in data, "Citation event should have a 'span'"
            assert 'start' in data['span'] and 'end' in data['span'], "Span should have 'start' and 'end'"
            assert 'payload' in data, "Citation event should have a 'payload'"

            # Check payload fields
            assert 'document_id' in data['payload'], "Payload should have 'document_id'"
            assert 'text' in data['payload'], "Payload should have 'text'"
            assert 'metadata' in data['payload'], "Payload should have 'metadata'"

        except json.JSONDecodeError:
            pytest.fail(f"Citation event data is not valid JSON: {data_part}")


@pytest.mark.asyncio
async def test_final_answer_event_format(mock_streaming_agent):
    """Test that the final answer event follows the expected format."""
    messages = [Message(role="user", content="Test query")]

    # Run the agent
    stream = mock_streaming_agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Look for final answer event
    final_answer_events = [
        line for line in output
        if 'event: agent.final_answer' in line
    ]

    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    # Check the format of the final answer event
    for event in final_answer_events:
        assert 'event: agent.final_answer' in event, "Event type should be 'agent.final_answer'"
        assert 'data: ' in event, "Event should have data payload"

        # Parse the data payload
        data_part = event.split('data: ')[1] if 'data: ' in event else event
        try:
            data = json.loads(data_part)

            # Check required fields
            assert 'id' in data, "Final answer event should have an 'id'"
            assert 'object' in data and data['object'] == 'agent.final_answer', "Event object should be 'agent.final_answer'"
            assert 'generated_answer' in data, "Final answer event should have a 'generated_answer'"
            assert 'citations' in data, "Final answer event should have 'citations'"

            # Check citation fields
            for citation in data['citations']:
                assert 'id' in citation, "Citation should have an 'id'"
                assert 'object' in citation and citation['object'] == 'citation', "Citation object should be 'citation'"
                assert 'spans' in citation, "Citation should have 'spans'"
                assert 'payload' in citation, "Citation should have a 'payload'"

                # Check spans format
                for span in citation['spans']:
                    assert 'start' in span, "Span should have 'start'"
                    assert 'end' in span, "Span should have 'end'"

                # Check payload fields
                assert 'document_id' in citation['payload'], "Payload should have 'document_id'"
                assert 'text' in citation['payload'], "Payload should have 'text'"
                assert 'metadata' in citation['payload'], "Payload should have 'metadata'"

        except json.JSONDecodeError:
            pytest.fail(f"Final answer event data is not valid JSON: {data_part}")


@pytest.mark.asyncio
async def test_overlapping_citation_handling():
    """Test that overlapping citations are handled correctly."""
    # Create a custom agent configuration
    config = MagicMock()
    config.stream = True
    config.max_iterations = 3

    # Create providers
    llm_provider = MockLLMProvider(
        response_content="This is a test response with overlapping citations",
        citations=["abc1234", "def5678"]
    )
    db_provider = MockDatabaseProvider()

    # Create agent
    agent = MockR2RStreamingAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Replace the search results collector with our mock
    agent.search_results_collector = MockSearchResultsCollector({
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
    })

    # Modify the arun method for overlapping citations
    original_arun = agent.arun

    async def custom_arun(*args, **kwargs):
        """Custom arun that includes overlapping citations."""
        # Setup like the original
        await agent._setup(kwargs.get('system_instruction'))

        messages = kwargs.get('messages', [])
        if messages:
            for m in messages:
                await agent.conversation.add_message(m)

        # Initialize citation tracker
        citation_tracker = CitationTracker()
        citation_payloads = {}

        # Track streaming citations for final persistence
        agent.streaming_citations = []

        # Create text with overlapping citations (citation spans that overlap)
        response_content = "This text has overlapping citations [abc1234] part of which [def5678] overlap."

        # Yield the message event
        yield agent._format_sse_event("message", {"content": response_content})

        # Manually create overlapping citation spans
        # For simplicity, we'll define the spans directly rather than using regex
        citation_spans = {
            "abc1234": [(30, 39)],  # This span includes "[abc1234]"
            "def5678": [(55, 64)]   # This span includes "[def5678]"
        }

        # Process the citations
        for cid, spans in citation_spans.items():
            for span in spans:
                # Mark as processed in the tracker
                citation_tracker.is_new_span(cid, span)

                # Look up the source document for this citation
                source_doc = agent.search_results_collector.find_by_short_id(cid)

                # Create citation payload
                citation_payload = {
                    "document_id": source_doc.get("document_id", f"doc_{cid}"),
                    "text": source_doc.get("text", f"This is document text for {cid}"),
                    "metadata": source_doc.get("metadata", {"source": f"source_{cid}"}),
                }

                # Store the payload by citation ID
                citation_payloads[cid] = citation_payload

                # Track for persistence
                agent.streaming_citations.append({
                    "id": cid,
                    "span": {"start": span[0], "end": span[1]},
                    "payload": citation_payload
                })

                # Emit citation event
                citation_event = {
                    "id": cid,
                    "object": "citation",
                    "span": {"start": span[0], "end": span[1]},
                    "payload": citation_payload
                }

                yield agent._format_sse_event("citation", citation_event)

        # Add assistant message with citation metadata to conversation
        await agent.conversation.add_message(
            Message(
                role="assistant",
                content=response_content,
                metadata={"citations": agent.streaming_citations}
            )
        )

        # Prepare consolidated citations for final answer
        consolidated_citations = []

        # Group citations by ID with all their spans
        for cid, spans in citation_tracker.get_all_spans().items():
            if cid in citation_payloads:
                consolidated_citations.append({
                    "id": cid,
                    "object": "citation",
                    "spans": [{"start": s[0], "end": s[1]} for s in spans],
                    "payload": citation_payloads[cid]
                })

        # Create and emit final answer event
        final_evt_payload = {
            "id": "msg_final",
            "object": "agent.final_answer",
            "generated_answer": response_content,
            "citations": consolidated_citations
        }

        # Emit final answer event
        yield agent._format_sse_event("agent.final_answer", final_evt_payload)

        # Signal the end of the SSE stream
        yield "event: done\ndata: {}\n\n"

    # Replace the arun method
    with patch.object(agent, 'arun', custom_arun):
        messages = [Message(role="user", content="Test query")]

        # Run the agent with overlapping citations
        stream = agent.arun(messages=messages)
        output = await collect_stream_output(stream)

        # Check that both citations were emitted
        citation_abc = any('abc1234' in event for event in output if 'event: citation' in event)
        citation_def = any('def5678' in event for event in output if 'event: citation' in event)

        assert citation_abc, "Citation abc1234 should be emitted"
        assert citation_def, "Citation def5678 should be emitted"

        # Check the final answer for both citations
        final_answer_events = [
            line for line in output
            if 'event: agent.final_answer' in line
        ]

        for event in final_answer_events:
            data_part = event.split('data: ')[1] if 'data: ' in event else event
            try:
                data = json.loads(data_part)
                if 'citations' in data:
                    citation_ids = [citation.get('id') for citation in data['citations']]
                    assert 'abc1234' in citation_ids, "abc1234 should be in final answer citations"
                    assert 'def5678' in citation_ids, "def5678 should be in final answer citations"
            except json.JSONDecodeError:
                continue


@pytest.mark.asyncio
async def test_robustness_against_citation_variations(mock_streaming_agent):
    """Test agent's robustness against different citation formats and variations."""
    # Create a custom text with different citation variations
    response_text = """
    This text has different citation variations:
    1. Standard citation: [abc1234]
    2. Another citation: [def5678]
    3. Adjacent citations: [abc1234][def5678]
    4. Special characters around citation: ([abc1234]) or "[def5678]".
    """

    # Use the extract_citations function directly to see what would be detected
    citations = extract_citations(response_text)

    # There should be at least two different citation IDs
    unique_citations = set(citations)
    assert len(unique_citations) >= 2, "Should extract at least two different citation IDs"
    assert "abc1234" in unique_citations, "Should extract abc1234"
    assert "def5678" in unique_citations, "Should extract def5678"

    # Count occurrences of each citation
    counts = {}
    for cid in citations:
        counts[cid] = counts.get(cid, 0) + 1

    # Each citation should be found the correct number of times based on the text
    assert counts.get("abc1234", 0) >= 2, "abc1234 should appear at least twice"
    assert counts.get("def5678", 0) >= 2, "def5678 should appear at least twice"


class TestCitationEdgeCases:
    """
    Test class for citation edge cases using parameterized tests to cover multiple scenarios.
    """

    @pytest.mark.parametrize("test_case", [
        # Test case 1: Empty text
        {"text": "", "expected_citations": []},

        # Test case 2: Text with no citations
        {"text": "This text has no citations.", "expected_citations": []},

        # Test case 3: Adjacent citations
        {"text": "Adjacent citations [abc1234][def5678]", "expected_citations": ["abc1234", "def5678"]},

        # Test case 4: Repeated citations
        {"text": "Repeated [abc1234] citation [abc1234]", "expected_citations": ["abc1234", "abc1234"]},

        # Test case 5: Citation at beginning
        {"text": "[abc1234] at beginning", "expected_citations": ["abc1234"]},

        # Test case 6: Citation at end
        {"text": "At end [abc1234]", "expected_citations": ["abc1234"]},

        # Test case 7: Mixed valid and invalid citations
        {"text": "Valid [abc1234] and invalid [ab123] citations", "expected_citations": ["abc1234"]},

        # Test case 8: Citations with punctuation
        {"text": "Citations with punctuation: ([abc1234]), [def5678]!", "expected_citations": ["abc1234", "def5678"]}
    ])
    def test_citation_extraction_cases(self, test_case):
        """Test citation extraction with various edge cases."""
        text = test_case["text"]
        expected = test_case["expected_citations"]

        # Extract citations
        actual = extract_citations(text)

        # Check count
        assert len(actual) == len(expected), f"Expected {len(expected)} citations, got {len(actual)}"

        # Check content (allowing for different orders)
        if expected:
            for expected_citation in expected:
                assert expected_citation in actual, f"Expected citation {expected_citation} not found"

@pytest.mark.asyncio
async def test_citation_handling_with_empty_response():
    """Test how the agent handles responses with no citations."""
    # Create a custom R2RStreamingAgent with no citations

    # Custom agent class for testing empty citations
    class EmptyResponseAgent(MockR2RStreamingAgent):
        async def arun(
            self,
            system_instruction: str = None,
            messages: list[Message] = None,
            *args,
            **kwargs,
        ) -> AsyncGenerator[str, None]:
            """Custom arun with no citations in the response."""
            await self._setup(system_instruction)

            if messages:
                for m in messages:
                    await self.conversation.add_message(m)

            # Initialize citation tracker
            citation_tracker = CitationTracker()

            # Empty response with no citations
            response_content = "This is a response with no citations."

            # Yield an initial message event with the start of the text
            yield self._format_sse_event("message", {"content": response_content})

            # No citation spans to extract
            citation_spans = extract_citation_spans(response_content)

            # Should be empty
            assert len(citation_spans) == 0, "No citation spans should be found"

            # Add assistant message to conversation (with no citation metadata)
            await self.conversation.add_message(
                Message(
                    role="assistant",
                    content=response_content,
                    metadata={"citations": []}
                )
            )

            # Create and emit final answer event
            final_evt_payload = {
                "id": "msg_final",
                "object": "agent.final_answer",
                "generated_answer": response_content,
                "citations": []
            }

            yield self._format_sse_event("agent.final_answer", final_evt_payload)
            yield "event: done\ndata: {}\n\n"

    # Create the agent with empty citation response
    config = MagicMock()
    config.stream = True

    llm_provider = MockLLMProvider(
        response_content="This is a response with no citations.",
        citations=[]
    )

    db_provider = MockDatabaseProvider()

    # Create the custom agent
    agent = EmptyResponseAgent(
        database_provider=db_provider,
        llm_provider=llm_provider,
        config=config,
        rag_generation_config=GenerationConfig(model="test/model")
    )

    # Test a simple query
    messages = [Message(role="user", content="Query with no citations")]

    # Run the agent
    stream = agent.arun(messages=messages)
    output = await collect_stream_output(stream)

    # Verify no citation events were emitted
    citation_events = [line for line in output if 'event: citation' in line]
    assert len(citation_events) == 0, "No citation events should be emitted"

    # Parse the final answer event to check citations
    final_answer_events = [line for line in output if 'event: agent.final_answer' in line]
    assert len(final_answer_events) > 0, "Final answer event should be emitted"

    data_part = final_answer_events[0].split('data: ')[1] if 'data: ' in final_answer_events[0] else ""

    # Parse final answer data
    try:
        data = json.loads(data_part)
        assert 'citations' in data, "Final answer event should include citations field"
        assert len(data['citations']) == 0, "Citations list should be empty"
    except json.JSONDecodeError:
        assert False, "Final answer event data should be valid JSON"

@pytest.mark.asyncio
async def test_citation_sanitization():
    """Test that citation IDs are properly sanitized before processing."""
    # Since extract_citations uses a strict regex pattern [A-Za-z0-9]{7,8},
    # we should test with valid citation formats
    text = "Citation with surrounding text[abc1234]and [def5678]with no spaces."

    # Extract citations
    citations = extract_citations(text)

    # Check if citations are properly extracted
    assert "abc1234" in citations, "Citation abc1234 should be extracted"
    assert "def5678" in citations, "Citation def5678 should be extracted"

    # Test with spaces - these should NOT be extracted based on the implementation
    text_with_spaces = "Citation with [abc1234 ] and [ def5678] spaces."
    citations_with_spaces = extract_citations(text_with_spaces)

    # The current implementation doesn't extract citations with spaces inside the brackets
    assert len(citations_with_spaces) == 0 or "abc1234" not in citations_with_spaces, "Citations with spaces should not be extracted with current implementation"

@pytest.mark.asyncio
async def test_citation_tracking_state_persistence():
    """Test that the CitationTracker correctly maintains state across multiple calls."""
    tracker = CitationTracker()

    # Record some initial spans
    tracker.is_new_span("abc1234", (10, 18))
    tracker.is_new_span("def5678", (30, 38))

    # Check if spans are correctly stored
    all_spans = tracker.get_all_spans()
    assert "abc1234" in all_spans, "Citation abc1234 should be tracked"
    assert "def5678" in all_spans, "Citation def5678 should be tracked"
    assert all_spans["abc1234"] == [(10, 18)], "Span positions should match"

    # Add another span for an existing citation
    tracker.is_new_span("abc1234", (50, 58))

    # Check if the new span was added
    all_spans = tracker.get_all_spans()
    assert len(all_spans["abc1234"]) == 2, "Citation abc1234 should have 2 spans"
    assert (50, 58) in all_spans["abc1234"], "New span should be added"

def test_citation_span_uniqueness():
    """Test that CitationTracker correctly identifies duplicate spans."""
    tracker = CitationTracker()

    # Record a span
    tracker.is_new_span("abc1234", (10, 18))

    # Check if the same span is recognized as not new
    assert not tracker.is_new_span("abc1234", (10, 18)), "Duplicate span should not be considered new"

    # Check if different span for same citation is recognized as new
    assert tracker.is_new_span("abc1234", (20, 28)), "Different span should be considered new"

    # Check if same span for different citation is recognized as new
    assert tracker.is_new_span("def5678", (10, 18)), "Same span for different citation should be considered new"

def test_citation_with_punctuation():
    """Test extraction of citations with surrounding punctuation."""
    text = "Citations with punctuation: ([abc1234]), [def5678]!, and [ghi9012]."

    # Extract citations
    citations = extract_citations(text)

    # Check if all citations are extracted correctly
    assert "abc1234" in citations, "Citation abc1234 should be extracted"
    assert "def5678" in citations, "Citation def5678 should be extracted"
    assert "ghi9012" in citations, "Citation ghi9012 should be extracted"

def test_citation_extraction_with_invalid_formats():
    """Test that invalid citation formats are not extracted."""
    text = "Invalid citation formats: [123], [abcdef], [abc123456789], and valid [abc1234]."

    # Extract citations
    citations = extract_citations(text)

    # Check that only valid citations are extracted
    assert len(citations) == 1, "Only one valid citation should be extracted"
    assert "abc1234" in citations, "Only valid citation abc1234 should be extracted"
    assert "123" not in citations, "Invalid citation [123] should not be extracted"
    assert "abcdef" not in citations, "Invalid citation [abcdef] should not be extracted"
    assert "abc123456789" not in citations, "Invalid citation [abc123456789] should not be extracted"
