# tests/conftest.py
import os

import pytest

from core.base import AppConfig, DatabaseConfig, VectorQuantizationType
from core.providers import NaClCryptoConfig, NaClCryptoProvider
from core.providers.database.postgres import (
    PostgresChunksHandler,
    PostgresCollectionsHandler,
    PostgresConversationsHandler,
    PostgresDatabaseProvider,
    PostgresDocumentsHandler,
    PostgresGraphsHandler,
    PostgresLimitsHandler,
    PostgresPromptsHandler,
)
from core.providers.database.users import (  # Make sure this import is correct
    PostgresUserHandler, )

TEST_DB_CONNECTION_STRING = os.environ.get(
    "TEST_DB_CONNECTION_STRING",
    "postgresql://postgres:postgres@localhost:5432/test_db",
)


@pytest.fixture
async def db_provider():
    crypto_provider = NaClCryptoProvider(NaClCryptoConfig(app={}))
    db_config = DatabaseConfig(
        app=AppConfig(project_name="test_project"),
        provider="postgres",
        connection_string=TEST_DB_CONNECTION_STRING,
        postgres_configuration_settings={
            "max_connections": 10,
            "statement_cache_size": 100,
        },
        project_name="test_project",
    )

    dimension = 4
    quantization_type = VectorQuantizationType.FP32

    db_provider = PostgresDatabaseProvider(db_config, dimension,
                                           crypto_provider, quantization_type)

    await db_provider.initialize()
    yield db_provider
    # Teardown logic if needed
    await db_provider.close()


@pytest.fixture
def crypto_provider():
    # Provide a crypto provider fixture if needed separately
    return NaClCryptoProvider(NaClCryptoConfig(app={}))


@pytest.fixture
async def chunks_handler(db_provider):
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresChunksHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def collections_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    config = db_provider.config

    handler = PostgresCollectionsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        config=config,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def conversations_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresConversationsHandler(project_name, connection_manager)
    await handler.create_tables()
    return handler


@pytest.fixture
async def documents_handler(db_provider):
    dimension = db_provider.dimension
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresDocumentsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def graphs_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type

    # If collections_handler is needed, you can depend on the collections_handler fixture
    # or pass None if it's optional.
    handler = PostgresGraphsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
        collections_handler=
        None,  # if needed, or await collections_handler fixture
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def limits_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    config = db_provider.config

    handler = PostgresLimitsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        config=config,
    )
    await handler.create_tables()
    # Optionally truncate
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('request_log')};")
    return handler


@pytest.fixture
async def users_handler(db_provider, crypto_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresUserHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        crypto_provider=crypto_provider,
    )
    await handler.create_tables()

    # Optionally clean up users table before each test
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('users')} CASCADE;")
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('users_api_keys')} CASCADE;")

    return handler


@pytest.fixture
async def prompt_handler(db_provider):
    """Returns an instance of PostgresPromptsHandler, creating the necessary
    tables first."""
    # from core.providers.database.postgres_prompts import PostgresPromptsHandler

    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresPromptsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        # You can specify a local prompt directory if desired
        prompt_directory=None,
    )
    # Create necessary tables and do initial prompt load
    await handler.create_tables()
    return handler


@pytest.fixture
async def graphs_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type

    # Optionally ensure 'collection_ids' column exists on your table(s), e.g.:
    create_col_sql = f"""
        ALTER TABLE "{project_name}"."graphs_entities"
        ADD COLUMN IF NOT EXISTS collection_ids UUID[] DEFAULT '{{}}';
    """
    await connection_manager.execute_query(create_col_sql)

    handler = PostgresGraphsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
        collections_handler=None,
    )
    await handler.create_tables()
    return handler

# Citation testing fixtures and utilities
import json
import re
from unittest.mock import MagicMock, AsyncMock
from typing import Tuple, Any, AsyncGenerator

from core.base import Message, LLMChatCompletion, LLMChatCompletionChunk, GenerationConfig
from core.utils import CitationTracker, SearchResultsCollector
from core.agent.base import R2RStreamingAgent


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

                    # Emit citation event in the expected format
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


from core.utils import extract_citation_spans, find_new_citation_spans
