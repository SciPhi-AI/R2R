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


# Add MockPostgresConnectionManager and MockPostgresPromptsHandler for testing prompts
class MockPostgresConnectionManager:
    """Mock connection manager for testing."""
    
    def __init__(self):
        """Initialize with in-memory database."""
        self.db = {'prompts': {}}
        self.next_id = 1
    
    async def execute_query(self, query, params=None):
        """Mock execute query."""
        # For simplicity, we'll just return success for all queries
        if 'DELETE' in query and params and len(params) > 0:
            name = params[0]
            if name in self.db['prompts']:
                del self.db['prompts'][name]
        return True
    
    async def fetchrow_query(self, query, params=None):
        """Mock fetchrow query."""
        # Parse the query to determine what to return
        if 'INSERT INTO' in query and 'RETURNING' in query:
            # Handle insert with returning
            prompt_id = self.next_id
            self.next_id += 1
            
            # For the prompts table insert
            if params and len(params) >= 3:
                name = params[0]
                template = params[1]
                input_types = params[2]
                
                # Store in our mock DB
                self.db['prompts'][name] = {
                    'id': prompt_id,
                    'name': name,
                    'template': template,
                    'input_types': input_types,
                    'created_at': '2023-01-01T00:00:00Z',
                    'updated_at': '2023-01-01T00:00:00Z'
                }
                
                return self.db['prompts'][name]
        
        elif 'UPDATE' in query and 'RETURNING' in query:
            # Handle update with returning
            if params and len(params) >= 2:
                # Last param is usually the name in UPDATE queries
                name = params[-1]
                
                if name in self.db['prompts']:
                    # Update the prompt
                    prompt = self.db['prompts'][name]
                    
                    # Handle different parameter formats based on the query
                    if 'template' in query.lower() and 'input_types' in query.lower():
                        # Update both template and input_types
                        prompt['template'] = params[0]
                        prompt['input_types'] = params[1]
                    elif 'template' in query.lower():
                        # Update only template
                        prompt['template'] = params[0]
                    elif 'input_types' in query.lower():
                        # Update only input_types
                        prompt['input_types'] = params[0]
                    
                    prompt['updated_at'] = '2023-01-01T00:00:01Z'
                    return prompt
        
        elif 'SELECT' in query:
            # Handle select queries
            if 'FROM' in query and 'WHERE' in query and params and len(params) > 0:
                value = params[0]
                
                if value in self.db['prompts']:
                    return self.db['prompts'][value]
            
        return None
    
    async def fetch_query(self, query, params=None):
        """Mock fetch query that returns multiple rows."""
        if 'SELECT' in query and 'FROM' in query:
            # Return all prompts
            return list(self.db['prompts'].values())
        
        return []


@pytest.fixture
async def mock_connection_manager():
    """Returns a mock connection manager."""
    return MockPostgresConnectionManager()


from core.providers.database.prompts_handler import PostgresPromptsHandler

# We extend the real handler, but override the methods that interact with the DB
class MockPostgresPromptsHandler(PostgresPromptsHandler):
    """Mock prompts handler for testing with in-memory storage."""
    
    def __init__(self, project_name, connection_manager, prompt_directory=None):
        """Initialize the handler with mock components."""
        super().__init__(project_name, connection_manager, prompt_directory)
        self._template_cache = {}
        self._prompt_cache = {}
        self.prompts = {}
    
    async def create_tables(self):
        """Mock create tables."""
        # No need to create real tables
        return
    
    async def _load_prompts(self):
        """Mock load prompts from database."""
        # Just initialize an empty dict
        self.prompts = {}
        return self.prompts
        
    async def add_prompt(self, name, template, input_types, preserve_existing=False):
        """Add or update a prompt in both in-memory store and database."""
        # Check if a prompt with the given name already exists
        existing_prompt = self.prompts.get(name)
        
        if existing_prompt and preserve_existing:
            # Skip adding if it already exists and we're preserving
            return
            
        # Insert or update the prompt in the database
        result = await self.connection_manager.fetchrow_query(
            "INSERT INTO prompts (name, template, input_types) VALUES ($1, $2, $3) RETURNING *",
            [name, template, input_types]
        )
        
        # Update the in-memory dictionary
        self.prompts[name] = {
            "name": name,
            "template": template,
            "input_types": input_types
        }
        
        # Clear any cached entries
        if name in self._template_cache:
            del self._template_cache[name]
            
        # Also clear formatted prompt cache
        keys_to_delete = []
        for key in self._prompt_cache:
            if key.startswith(f"{name}:"):
                keys_to_delete.append(key)
                
        for key in keys_to_delete:
            del self._prompt_cache[key]
    
    async def update_prompt(self, name, template=None, input_types=None):
        """Update a prompt in both the database and in-memory."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
            
        current = self.prompts[name]
        update_template = template if template is not None else current["template"]
        update_input_types = input_types if input_types is not None else current["input_types"]
        
        # Update the database
        if template is not None and input_types is not None:
            result = await self.connection_manager.fetchrow_query(
                "UPDATE prompts SET template=$1, input_types=$2 WHERE name=$3 RETURNING *",
                [update_template, update_input_types, name]
            )
        elif template is not None:
            result = await self.connection_manager.fetchrow_query(
                "UPDATE prompts SET template=$1 WHERE name=$2 RETURNING *",
                [update_template, name]
            )
        elif input_types is not None:
            result = await self.connection_manager.fetchrow_query(
                "UPDATE prompts SET input_types=$1 WHERE name=$2 RETURNING *",
                [update_input_types, name]
            )
            
        # Update the in-memory dict
        self.prompts[name] = {
            "name": name,
            "template": update_template,
            "input_types": update_input_types
        }
        
        # Clear any cached templates
        if name in self._template_cache:
            del self._template_cache[name]
            
        # Clear any cached formatted prompts
        keys_to_delete = []
        for key in self._prompt_cache:
            if key.startswith(f"{name}:"):
                keys_to_delete.append(key)
                
        for key in keys_to_delete:
            del self._prompt_cache[key]
    
    async def get_prompt(self, name):
        """Get a prompt from in-memory dictionary or raises ValueError."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
        return self.prompts[name]
    
    async def delete_prompt(self, name):
        """Delete a prompt from both the database and in-memory state."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
            
        # Delete from the database
        await self.connection_manager.execute_query(
            "DELETE FROM prompts WHERE name=$1",
            [name]
        )
        
        # Remove from in-memory dictionary
        del self.prompts[name]
        
        # Clear from template cache
        if name in self._template_cache:
            del self._template_cache[name]
            
        # Clear from prompt cache
        keys_to_delete = []
        for key in self._prompt_cache:
            if key.startswith(f"{name}:"):
                keys_to_delete.append(key)
                
        for key in keys_to_delete:
            del self._prompt_cache[key]
    
    def _cache_key(self, prompt_name, inputs):
        """Generate a cache key for the prompt with inputs."""
        inputs_str = ",".join(f"{k}:{v}" for k, v in sorted(inputs.items()))
        return f"{prompt_name}:{inputs_str}"
    
    async def get_cached_prompt(self, prompt_name, inputs=None, bypass_cache=False):
        """Get a cached formatted prompt or generate one."""
        if inputs is None:
            inputs = {}
            
        # Generate cache key
        cache_key = self._cache_key(prompt_name, inputs)
        
        # Check prompt cache
        if not bypass_cache and cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]
            
        # Check if template is cached
        if prompt_name not in self._template_cache or bypass_cache:
            # If we're bypassing cache, we need to query the database directly
            if bypass_cache:
                # Get the template directly from the connection manager to simulate a DB query
                db_result = self.connection_manager.db['prompts'].get(prompt_name)
                if db_result:
                    template = db_result['template']
                    input_types = db_result['input_types']
                    self._template_cache[prompt_name] = {"template": template, "input_types": input_types}
                else:
                    # If not found in DB, raise error
                    raise ValueError(f"Prompt template '{prompt_name}' not found")
            else:
                # Load the template from our in-memory store
                prompt_info = await self.get_prompt(prompt_name)
                self._template_cache[prompt_name] = prompt_info
        
        # Get template and format it
        template_info = self._template_cache[prompt_name]
        template = template_info["template"]
        
        # Format the template with inputs
        formatted = template.format(**inputs)
        
        # Cache the formatted prompt
        self._prompt_cache[cache_key] = formatted
        
        return formatted

@pytest.fixture
async def mock_prompt_handler(mock_connection_manager):
    """Returns a mock prompts handler for testing."""
    handler = MockPostgresPromptsHandler(
        project_name="test_project",
        connection_manager=mock_connection_manager,
        prompt_directory=None,
    )
    # Initialize without connecting to DB
    await handler.create_tables()
    return handler
