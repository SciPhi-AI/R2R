# tests/conftest.py
import os
import json
from datetime import datetime
import uuid

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
        """Initialize the connection manager."""
        self.log = []
        self.db = {
            "prompts": {},
        }

    async def fetchrow_query(self, query, params=None):
        """Mock fetchrow query."""
        self.log.append({"type": "fetchrow", "query": query, "params": params})

        # Handle INSERT or UPDATE operations
        if "INSERT" in query.upper() or "UPDATE" in query.upper():
            if "prompts" in query:
                now = datetime.now()
                
                # Handle different query types
                if "INSERT" in query.upper():
                    # Handle INSERT queries (add_prompt)
                    name = params[0]
                    template = params[1]
                    input_types = params[2]
                    
                    # Create or update in mock DB
                    if name not in self.db["prompts"]:
                        self.db["prompts"][name] = {
                            "name": name,
                            "template": template,
                            "input_types": input_types,
                            "created_at": now,
                            "updated_at": now,
                        }
                    else:
                        self.db["prompts"][name]["template"] = template
                        self.db["prompts"][name]["input_types"] = input_types
                        self.db["prompts"][name]["updated_at"] = now
                    
                    return self.db["prompts"][name]
                
                elif "UPDATE" in query.upper():
                    # Handle UPDATE queries (update_prompt)
                    if "SET template" in query and "input_types" not in query:
                        # Only updating template
                        template = params[0]
                        name = params[1]
                        
                        if name in self.db["prompts"]:
                            self.db["prompts"][name]["template"] = template
                            self.db["prompts"][name]["updated_at"] = now
                            return self.db["prompts"][name]
                    
                    elif "SET input_types" in query and "template" not in query:
                        # Only updating input_types
                        input_types = params[0]
                        name = params[1]
                        
                        if name in self.db["prompts"]:
                            self.db["prompts"][name]["input_types"] = input_types
                            self.db["prompts"][name]["updated_at"] = now
                            return self.db["prompts"][name]
                    
                    elif "SET template" in query and "input_types" in query:
                        # Updating both template and input_types
                        template = params[0]
                        input_types = params[1]
                        name = params[2]
                        
                        if name in self.db["prompts"]:
                            self.db["prompts"][name]["template"] = template
                            self.db["prompts"][name]["input_types"] = input_types
                            self.db["prompts"][name]["updated_at"] = now
                            return self.db["prompts"][name]
            
            # Handle DELETE operations
            elif "DELETE" in query.upper():
                if "prompts" in query:
                    name = params[0]
                    if name in self.db["prompts"]:
                        del self.db["prompts"][name]
                    return {"deleted": True}

        # Handle SELECT operations
        elif "SELECT" in query.upper():
            if "prompts" in query and "WHERE name" in query:
                name = params[0]
                if name in self.db["prompts"]:
                    return self.db["prompts"][name]
            
            # Handle listing all prompts
            elif "prompts" in query and "WHERE name" not in query:
                return list(self.db["prompts"].values())

        return None

    async def fetch_query(self, query, params=None):
        """Mock fetch query."""
        self.log.append({"type": "fetch", "query": query, "params": params})
        
        if "SELECT" in query.upper() and "prompts" in query:
            if params and len(params) > 0:
                # Filter by name if provided
                name = params[0]
                if name in self.db["prompts"]:
                    return [self.db["prompts"][name]]
                return []
            else:
                # Return all prompts
                return list(self.db["prompts"].values())
        
        return []

    async def execute_query(self, query, params=None):
        """Mock execute query."""
        self.log.append({"type": "execute", "query": query, "params": params})
        
        if "CREATE TABLE" in query.upper():
            return {"created": True}
        
        elif "DELETE" in query.upper():
            if "prompts" in query:
                name = params[0]
                if name in self.db["prompts"]:
                    del self.db["prompts"][name]
                return {"deleted": True}
        
        return None

    async def close(self):
        """Mock close."""
        pass


class MockPostgresPromptsHandler:
    """Mock PostgreSQL prompts handler for testing."""

    def __init__(self, project_name, connection_manager):
        """Initialize the handler."""
        self.project_name = project_name
        self.connection_manager = connection_manager
        self.prompts = {}  # In-memory store of prompts
        self.cache = {}    # Cache for formatted prompts
        self._template_cache = {}  
        self._prompt_cache = {}    # For compatibility with existing tests
        
    def _get_table_name(self, table):
        """Get table name."""
        return f"{self.project_name}.{table}"
        
    async def create_tables(self):
        """Create the necessary tables."""
        # Simply record this was called - no actual table creation needed
        await self.connection_manager.execute_query(
            "CREATE TABLE IF NOT EXISTS..."
        )
        
    def _cache_key(self, prompt_name, inputs):
        """Generate a cache key for a prompt and inputs."""
        if not inputs:
            return prompt_name
        inputs_str = json.dumps(inputs, sort_keys=True)
        return f"{prompt_name}:{inputs_str}"
    
    async def add_prompt(self, name, template, input_types, preserve_existing=False):
        """Add a prompt to the database."""
        # Check if prompt exists and we should preserve it
        if preserve_existing and name in self.prompts:
            return
            
        # Insert or update in database
        query = f"""
            INSERT INTO {self._get_table_name('prompts')} (name, template, input_types)
            VALUES ($1, $2, $3)
            ON CONFLICT (name) 
            DO UPDATE SET template = $2, input_types = $3, updated_at = NOW()
            RETURNING *
        """
        
        result = await self.connection_manager.fetchrow_query(
            query, [name, template, input_types]
        )
        
        if result:
            # Update in-memory state
            self.prompts[name] = {
                "name": name,
                "template": template,
                "input_types": input_types,
                "created_at": result.get("created_at", datetime.now()),
                "updated_at": result.get("updated_at", datetime.now()),
            }
            
            # Clear any cached formatted prompts for this name
            self._clear_prompt_from_cache(name)
    
    def _clear_prompt_from_cache(self, prompt_name):
        """Clear all cached entries for a specific prompt."""
        # Clear from cache dictionary
        keys_to_remove = []
        for key in self.cache:
            if key == prompt_name or key.startswith(f"{prompt_name}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
            
        # Also clear from _prompt_cache for test compatibility
        prompt_cache_keys = []
        for key in self._prompt_cache:
            if key.startswith(f"{prompt_name}:"):
                prompt_cache_keys.append(key)
                
        for key in prompt_cache_keys:
            del self._prompt_cache[key]
            
        # Remove from _template_cache too
        if prompt_name in self._template_cache:
            del self._template_cache[prompt_name]
    
    async def update_prompt(self, name, template=None, input_types=None):
        """Update a prompt in the database."""
        if name not in self.prompts:
            raise ValueError(f"Prompt template '{name}' not found")
            
        # Determine what to update
        if template is not None and input_types is not None:
            # Update both template and input_types
            query = f"""
                UPDATE {self._get_table_name('prompts')} 
                SET template = $1, input_types = $2 
                WHERE name = $3 
                RETURNING *
            """
            params = [template, input_types, name]
        elif template is not None:
            # Update only template
            query = f"""
                UPDATE {self._get_table_name('prompts')} 
                SET template = $1 
                WHERE name = $2 
                RETURNING *
            """
            params = [template, name]
        elif input_types is not None:
            # Update only input_types
            query = f"""
                UPDATE {self._get_table_name('prompts')} 
                SET input_types = $1 
                WHERE name = $2 
                RETURNING *
            """
            params = [input_types, name]
        else:
            # Nothing to update
            return
            
        # Execute query
        result = await self.connection_manager.fetchrow_query(query, params)
        
        if result:
            # Update in-memory state with the changes
            if template is not None:
                self.prompts[name]["template"] = template
                # Update template cache for test compatibility
                self._template_cache[name] = {"template": template}
            if input_types is not None:
                self.prompts[name]["input_types"] = input_types
            self.prompts[name]["updated_at"] = datetime.now()
            
            # Clear cache entries for this prompt
            self._clear_prompt_from_cache(name)
    
    async def delete_prompt(self, name):
        """Delete a prompt from the database."""
        if name not in self.prompts:
            return False
            
        # Delete from database
        query = f"""
            DELETE FROM {self._get_table_name('prompts')} 
            WHERE name = $1
            RETURNING *
        """
        
        result = await self.connection_manager.execute_query(query, [name])
        
        # Delete from in-memory state if successful
        if result:
            if name in self.prompts:
                del self.prompts[name]
            self._clear_prompt_from_cache(name)
            return True
        return False
    
    async def get_prompt(self, name):
        """Get a prompt from the database."""
        if name in self.prompts:
            return self.prompts[name]
            
        # Try to get from database
        query = f"""
            SELECT * FROM {self._get_table_name('prompts')} WHERE name = $1
        """
        
        result = await self.connection_manager.fetchrow_query(query, [name])
        
        if result:
            # Update in-memory state
            self.prompts[name] = result
            return result
            
        raise ValueError(f"Prompt template '{name}' not found")
        
    async def list_prompts(self):
        """List all prompts."""
        # Get from database to ensure we have latest
        query = f"""
            SELECT * FROM {self._get_table_name('prompts')}
        """
        
        results = await self.connection_manager.fetch_query(query)
        
        # Update in-memory state
        for result in results:
            self.prompts[result["name"]] = result
            
        return list(self.prompts.values())
    
    async def load_prompts_from_yaml(self, yaml_content):
        """Load prompts from a YAML string."""
        # Just a stub for testing
        pass
        
    async def get_cached_prompt(self, prompt_name, inputs=None, bypass_cache=False):
        """Get a formatted prompt, using cache if available."""
        if inputs is None:
            inputs = {}
        
        # Generate cache key
        cache_key = self._cache_key(prompt_name, inputs)
        
        # Check cache if not bypassing
        if not bypass_cache and cache_key in self.cache:
            return self.cache[cache_key]
        
        # Get prompt data from the DB if bypassing cache
        if bypass_cache:
            query = f"""
                SELECT * FROM {self._get_table_name('prompts')} WHERE name = $1
            """
            db_data = await self.connection_manager.fetchrow_query(query, [prompt_name])
            if db_data:
                template = db_data["template"]
                # Update template cache for test compatibility
                self._template_cache[prompt_name] = {"template": template}
            else:
                raise ValueError(f"Prompt template '{prompt_name}' not found")
        else:
            # Get from in-memory store
            if prompt_name not in self.prompts:
                raise ValueError(f"Prompt template '{prompt_name}' not found")
            template = self.prompts[prompt_name]["template"]
            # Update template cache for test compatibility
            self._template_cache[prompt_name] = {"template": template}
        
        # Format the template
        formatted = template
        if inputs:
            formatted = template.format(**inputs)
        
        # Cache the result
        self.cache[cache_key] = formatted
        # Also update prompt cache for test compatibility
        self._prompt_cache[cache_key] = formatted
        
        return formatted


@pytest.fixture
async def mock_connection_manager():
    """Returns a mock connection manager for testing."""
    return MockPostgresConnectionManager()


@pytest.fixture
async def mock_prompt_handler(mock_connection_manager):
    """Returns a mock prompts handler for testing."""
    handler = MockPostgresPromptsHandler(
        project_name="test_project",
        connection_manager=mock_connection_manager,
    )
    # Initialize without connecting to DB
    await handler.create_tables()
    return handler
