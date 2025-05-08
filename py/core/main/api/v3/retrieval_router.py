import logging
import textwrap
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import Body, Depends
from fastapi.responses import StreamingResponse

from core.base import (
    GenerationConfig,
    Message,
    R2RException,
    SearchMode,
    SearchSettings,
    select_search_filters,
)
from core.base.api.models import (
    WrappedAgentResponse,
    WrappedCompletionResponse,
    WrappedEmbeddingResponse,
    WrappedLLMChatCompletion,
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger(__name__)


def merge_search_settings(
    base: SearchSettings, overrides: SearchSettings
) -> SearchSettings:
    # Convert both to dict
    base_dict = base.model_dump()
    overrides_dict = overrides.model_dump(exclude_unset=True)

    # Update base_dict with values from overrides_dict
    # This ensures that any field set in overrides takes precedence
    for k, v in overrides_dict.items():
        base_dict[k] = v

    # Construct a new SearchSettings from the merged dict
    return SearchSettings(**base_dict)


class RetrievalRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing RetrievalRouter")
        super().__init__(providers, services, config)

    def _register_workflows(self):
        pass

    def _prepare_search_settings(
        self,
        auth_user: Any,
        search_mode: SearchMode,
        search_settings: Optional[SearchSettings],
    ) -> SearchSettings:
        """Prepare the effective search settings based on the provided
        search_mode, optional user-overrides in search_settings, and applied
        filters."""
        if search_mode != SearchMode.custom:
            # Start from mode defaults
            effective_settings = SearchSettings.get_default(search_mode.value)
            if search_settings:
                # Merge user-provided overrides
                effective_settings = merge_search_settings(
                    effective_settings, search_settings
                )
        else:
            # Custom mode: use provided settings or defaults
            effective_settings = search_settings or SearchSettings()

        # Apply user-specific filters
        effective_settings.filters = select_search_filters(
            auth_user, effective_settings
        )
        return effective_settings

    def _setup_routes(self):
        @self.router.post(
            "/retrieval/search",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Search R2R",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient()
                            # if using auth, do client.login(...)

                            response = client.retrieval.search(
                                query="What is DeepSeek R1?",
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // if using auth, do client.login(...)

                            const response = await client.retrieval.search({
                                query: "What is DeepSeek R1?",
                            });
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            # Basic search
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/search" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "query": "What is DeepSeek R1?"
                            }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def search_app(
            query: str = Body(
                ...,
                description="Search query to find relevant documents",
            ),
            search_mode: SearchMode = Body(
                default=SearchMode.custom,
                description=(
                    "Default value of `custom` allows full control over search settings.\n\n"
                    "Pre-configured search modes:\n"
                    "`basic`: A simple semantic-based search.\n"
                    "`advanced`: A more powerful hybrid search combining semantic and full-text.\n"
                    "`custom`: Full control via `search_settings`.\n\n"
                    "If `filters` or `limit` are provided alongside `basic` or `advanced`, "
                    "they will override the default settings for that mode."
                ),
            ),
            search_settings: Optional[SearchSettings] = Body(
                None,
                description=(
                    "The search configuration object. If `search_mode` is `custom`, "
                    "these settings are used as-is. For `basic` or `advanced`, these settings will override the default mode configuration.\n\n"
                    "Common overrides include `filters` to narrow results and `limit` to control how many results are returned."
                ),
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedSearchResponse:
            """Perform a search query against vector and/or graph-based
            databases.

            **Search Modes:**
            - `basic`: Defaults to semantic search. Simple and easy to use.
            - `advanced`: Combines semantic search with full-text search for more comprehensive results.
            - `custom`: Complete control over how search is performed. Provide a full `SearchSettings` object.

            **Filters:**
            Apply filters directly inside `search_settings.filters`. For example:
            ```json
            {
            "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}}
            }
            ```
            Supported operators: `$eq`, `$neq`, `$gt`, `$gte`, `$lt`, `$lte`, `$like`, `$ilike`, `$in`, `$nin`.

            **Hybrid Search:**
            Enable hybrid search by setting `use_hybrid_search: true` in search_settings. This combines semantic search with
            keyword-based search for improved results. Configure with `hybrid_settings`:
            ```json
            {
            "use_hybrid_search": true,
            "hybrid_settings": {
                "full_text_weight": 1.0,
                "semantic_weight": 5.0,
                "full_text_limit": 200,
                "rrf_k": 50
            }
            }
            ```

            **Graph-Enhanced Search:**
            Knowledge graph integration is enabled by default. Control with `graph_search_settings`:
            ```json
            {
            "graph_search_settings": {
                "use_graph_search": true,
                "kg_search_type": "local"
            }
            }
            ```

            **Advanced Filtering:**
            Use complex filters to narrow down results by metadata fields or document properties:
            ```json
            {
            "filters": {
                "$and":[
                    {"document_type": {"$eq": "pdf"}},
                    {"metadata.year": {"$gt": 2020}}
                ]
            }
            }
            ```

            **Results:**
            The response includes vector search results and optional graph search results.
            Each result contains the matched text, document ID, and relevance score.

            """
            if not query:
                raise R2RException("Query cannot be empty", 400)
            effective_settings = self._prepare_search_settings(
                auth_user, search_mode, search_settings
            )
            results = await self.services.retrieval.search(
                query=query,
                search_settings=effective_settings,
            )
            return results  # type: ignore

        @self.router.post(
            "/retrieval/rag",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="RAG Query",
            response_model=None,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            # Basic RAG request
                            response = client.retrieval.rag(
                                query="What is DeepSeek R1?",
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // when using auth, do client.login(...)

                            // Basic RAG request
                            const response = await client.retrieval.rag({
                                query: "What is DeepSeek R1?",
                            });
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            # Basic RAG request
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/rag" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "query": "What is DeepSeek R1?"
                            }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def rag_app(
            query: str = Body(...),
            search_mode: SearchMode = Body(
                default=SearchMode.custom,
                description=(
                    "Default value of `custom` allows full control over search settings.\n\n"
                    "Pre-configured search modes:\n"
                    "`basic`: A simple semantic-based search.\n"
                    "`advanced`: A more powerful hybrid search combining semantic and full-text.\n"
                    "`custom`: Full control via `search_settings`.\n\n"
                    "If `filters` or `limit` are provided alongside `basic` or `advanced`, "
                    "they will override the default settings for that mode."
                ),
            ),
            search_settings: Optional[SearchSettings] = Body(
                None,
                description=(
                    "The search configuration object. If `search_mode` is `custom`, "
                    "these settings are used as-is. For `basic` or `advanced`, these settings will override the default mode configuration.\n\n"
                    "Common overrides include `filters` to narrow results and `limit` to control how many results are returned."
                ),
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="Configuration for RAG generation",
            ),
            task_prompt: Optional[str] = Body(
                default=None,
                description="Optional custom prompt to override default",
            ),
            include_title_if_available: bool = Body(
                default=False,
                description="Include document titles in responses when available",
            ),
            include_web_search: bool = Body(
                default=False,
                description="Include web search results provided to the LLM.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedRAGResponse:
            """Execute a RAG (Retrieval-Augmented Generation) query.

            This endpoint combines search results with language model generation to produce accurate,
            contextually-relevant responses based on your document corpus.

            **Features:**
            - Combines vector search, optional knowledge graph integration, and LLM generation
            - Automatically cites sources with unique citation identifiers
            - Supports both streaming and non-streaming responses
            - Compatible with various LLM providers (OpenAI, Anthropic, etc.)
            - Web search integration for up-to-date information

            **Search Configuration:**
            All search parameters from the search endpoint apply here, including filters, hybrid search, and graph-enhanced search.

            **Generation Configuration:**
            Fine-tune the language model's behavior with `rag_generation_config`:
            ```json
            {
                "model": "openai/gpt-4o-mini",  // Model to use
                "temperature": 0.7,              // Control randomness (0-1)
                "max_tokens": 1500,              // Maximum output length
                "stream": true                   // Enable token streaming
            }
            ```

            **Model Support:**
            - OpenAI models (default)
            - Anthropic Claude models (requires ANTHROPIC_API_KEY)
            - Local models via Ollama
            - Any provider supported by LiteLLM

            **Streaming Responses:**
            When `stream: true` is set, the endpoint returns Server-Sent Events with the following types:
            - `search_results`: Initial search results from your documents
            - `message`: Partial tokens as they're generated
            - `citation`: Citation metadata when sources are referenced
            - `final_answer`: Complete answer with structured citations

            **Example Response:**
            ```json
            {
            "generated_answer": "DeepSeek-R1 is a model that demonstrates impressive performance...[1]",
            "search_results": { ... },
            "citations": [
                {
                    "id": "cit.123456",
                    "object": "citation",
                    "payload": { ... }
                }
            ]
            }
            ```
            """

            if "model" not in rag_generation_config.model_fields_set:
                rag_generation_config.model = self.config.app.quality_llm

            effective_settings = self._prepare_search_settings(
                auth_user, search_mode, search_settings
            )

            response = await self.services.retrieval.rag(
                query=query,
                search_settings=effective_settings,
                rag_generation_config=rag_generation_config,
                task_prompt=task_prompt,
                include_title_if_available=include_title_if_available,
                include_web_search=include_web_search,
            )

            if rag_generation_config.stream:
                # ========== Streaming path ==========
                async def stream_generator():
                    try:
                        async for chunk in response:
                            if len(chunk) > 1024:
                                for i in range(0, len(chunk), 1024):
                                    yield chunk[i : i + 1024]
                            else:
                                yield chunk
                    except GeneratorExit:
                        # Clean up if needed, then return
                        return

                return StreamingResponse(
                    stream_generator(), media_type="text/event-stream"
                )  # type: ignore
            else:
                return response

        @self.router.post(
            "/retrieval/agent",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="RAG-powered Conversational Agent",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import (
                                R2RClient,
                                ThinkingEvent,
                                ToolCallEvent,
                                ToolResultEvent,
                                CitationEvent,
                                FinalAnswerEvent,
                                MessageEvent,
                            )

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            # Basic synchronous request
                            response = client.retrieval.agent(
                                message={
                                    "role": "user",
                                    "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
                                },
                                rag_tools=["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"],
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // when using auth, do client.login(...)

                            async function main() {
                                // Basic synchronous request
                                const ragResponse = await client.retrieval.agent({
                                    message: {
                                        role: "user",
                                        content: "Do a deep analysis of the philosophical implications of DeepSeek R1"
                                    },
                                    ragTools: ["web_search", "web_scrape", "search_file_descriptions", "search_file_knowledge", "get_file_content"]
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            # Basic request
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "message": {
                                    "role": "user",
                                    "content": "What were the key contributions of Aristotle to logic?"
                                },
                                "search_settings": {
                                    "use_semantic_search": true,
                                    "filters": {"document_id": {"$eq": "e43864f5-a36f-548e-aacd-6f8d48b30c7f"}}
                                },
                                "rag_tools": ["search_file_knowledge", "get_file_content", "web_search"]
                            }'

                            # Advanced analysis with extended thinking
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "message": {
                                    "role": "user",
                                    "content": "Do a deep analysis of the philosophical implications of DeepSeek R1"
                                },
                                "search_settings": {"limit": 20},
                                "research_tools": ["rag", "reasoning", "critique", "python_executor"],
                                "rag_generation_config": {
                                    "model": "anthropic/claude-3-7-sonnet-20250219",
                                    "extended_thinking": true,
                                    "thinking_budget": 4096,
                                    "temperature": 1,
                                    "top_p": null,
                                    "max_tokens": 16000,
                                    "stream": False
                                }
                            }'

                            # Conversation continuation
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/agent" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "message": {
                                    "role": "user",
                                    "content": "How does it compare to other reasoning models?"
                                },
                                "conversation_id": "YOUR_CONVERSATION_ID"
                            }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def agent_app(
            message: Optional[Message] = Body(
                None,
                description="Current message to process",
            ),
            messages: Optional[list[Message]] = Body(
                None,
                deprecated=True,
                description="List of messages (deprecated, use message instead)",
            ),
            search_mode: SearchMode = Body(
                default=SearchMode.custom,
                description="Pre-configured search modes: basic, advanced, or custom.",
            ),
            search_settings: Optional[SearchSettings] = Body(
                None,
                description="The search configuration object for retrieving context.",
            ),
            # Generation configurations
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="Configuration for RAG generation in 'rag' mode",
            ),
            research_generation_config: Optional[GenerationConfig] = Body(
                None,
                description="Configuration for generation in 'research' mode. If not provided but mode='research', rag_generation_config will be used with appropriate model overrides.",
            ),
            # Tool configurations
            # FIXME: We need a more generic way to handle this
            rag_tools: Optional[
                list[
                    Literal[
                        "web_search",
                        "web_scrape",
                        "search_file_descriptions",
                        "search_file_knowledge",
                        "get_file_content",
                    ]
                ]
            ] = Body(
                None,
                description="List of tools to enable for RAG mode. Available tools: search_file_knowledge, get_file_content, web_search, web_scrape, search_file_descriptions",
            ),
            # FIXME: We need a more generic way to handle this
            research_tools: Optional[
                list[
                    Literal["rag", "reasoning", "critique", "python_executor"]
                ]
            ] = Body(
                None,
                description="List of tools to enable for Research mode. Available tools: rag, reasoning, critique, python_executor",
            ),
            # Backward compatibility
            task_prompt: Optional[str] = Body(
                default=None,
                description="Optional custom prompt to override default",
            ),
            # Backward compatibility
            include_title_if_available: bool = Body(
                default=True,
                description="Pass document titles from search results into the LLM context window.",
            ),
            conversation_id: Optional[UUID] = Body(
                default=None,
                description="ID of the conversation",
            ),
            max_tool_context_length: Optional[int] = Body(
                default=32_768,
                description="Maximum length of returned tool context",
            ),
            use_system_context: Optional[bool] = Body(
                default=True,
                description="Use extended prompt for generation",
            ),
            # FIXME: We need a more generic way to handle this
            mode: Optional[Literal["rag", "research"]] = Body(
                default="rag",
                description="Mode to use for generation: 'rag' for standard retrieval or 'research' for deep analysis with reasoning capabilities",
            ),
            needs_initial_conversation_name: Optional[bool] = Body(
                default=None,
                description="If true, the system will automatically assign a conversation name if not already specified previously.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedAgentResponse:
            """
            Engage with an intelligent agent for information retrieval, analysis, and research.

            This endpoint offers two operating modes:
            - **RAG mode**: Standard retrieval-augmented generation for answering questions based on knowledge base
            - **Research mode**: Advanced capabilities for deep analysis, reasoning, and computation

            ### RAG Mode (Default)

            The RAG mode provides fast, knowledge-based responses using:
            - Semantic and hybrid search capabilities
            - Document-level and chunk-level content retrieval
            - Optional web search integration
            - Source citation and evidence-based responses

            ### Research Mode

            The Research mode builds on RAG capabilities and adds:
            - A dedicated reasoning system for complex problem-solving
            - Critique capabilities to identify potential biases or logical fallacies
            - Python execution for computational analysis
            - Multi-step reasoning for deeper exploration of topics

            ### Available Tools

            **RAG Tools:**
            - `search_file_knowledge`: Semantic/hybrid search on your ingested documents
            - `search_file_descriptions`: Search over file-level metadata
            - `content`: Fetch entire documents or chunk structures
            - `web_search`: Query external search APIs for up-to-date information
            - `web_scrape`: Scrape and extract content from specific web pages

            **Research Tools:**
            - `rag`: Leverage the underlying RAG agent for information retrieval
            - `reasoning`: Call a dedicated model for complex analytical thinking
            - `critique`: Analyze conversation history to identify flaws and biases
            - `python_executor`: Execute Python code for complex calculations and analysis

            ### Streaming Output

            When streaming is enabled, the agent produces different event types:
            - `thinking`: Shows the model's step-by-step reasoning (when extended_thinking=true)
            - `tool_call`: Shows when the agent invokes a tool
            - `tool_result`: Shows the result of a tool call
            - `citation`: Indicates when a citation is added to the response
            - `message`: Streams partial tokens of the response
            - `final_answer`: Contains the complete generated answer and structured citations

            ### Conversations

            Maintain context across multiple turns by including `conversation_id` in each request.
            After your first call, store the returned `conversation_id` and include it in subsequent calls.
            If no conversation name has already been set for the conversation, the system will automatically assign one.

            """
            # Handle model selection based on mode
            if "model" not in rag_generation_config.model_fields_set:
                if mode == "rag":
                    rag_generation_config.model = self.config.app.quality_llm
                elif mode == "research":
                    rag_generation_config.model = self.config.app.planning_llm

            # Prepare search settings
            effective_settings = self._prepare_search_settings(
                auth_user, search_mode, search_settings
            )

            # Determine effective generation config
            effective_generation_config = rag_generation_config
            if mode == "research" and research_generation_config:
                effective_generation_config = research_generation_config

            try:
                response = await self.services.retrieval.agent(
                    message=message,
                    messages=messages,
                    search_settings=effective_settings,
                    rag_generation_config=rag_generation_config,
                    research_generation_config=research_generation_config,
                    task_prompt=task_prompt,
                    include_title_if_available=include_title_if_available,
                    max_tool_context_length=max_tool_context_length or 32_768,
                    conversation_id=(
                        str(conversation_id) if conversation_id else None  # type: ignore
                    ),
                    use_system_context=use_system_context
                    if use_system_context is not None
                    else True,
                    rag_tools=rag_tools,  # type: ignore
                    research_tools=research_tools,  # type: ignore
                    mode=mode,
                    needs_initial_conversation_name=needs_initial_conversation_name,
                )

                if effective_generation_config.stream:

                    async def stream_generator():
                        try:
                            async for chunk in response:
                                if len(chunk) > 1024:
                                    for i in range(0, len(chunk), 1024):
                                        yield chunk[i : i + 1024]
                                else:
                                    yield chunk
                        except GeneratorExit:
                            # Clean up if needed, then return
                            return

                    return StreamingResponse(  # type: ignore
                        stream_generator(), media_type="text/event-stream"
                    )
                else:
                    return response
            except Exception as e:
                logger.error(f"Error in agent_app: {e}")
                raise R2RException(str(e), 500) from e

        @self.router.post(
            "/retrieval/completion",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Generate Message Completions",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.completion(
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": "What is the capital of France?"},
                                    {"role": "assistant", "content": "The capital of France is Paris."},
                                    {"role": "user", "content": "What about Italy?"}
                                ],
                                generation_config={
                                    "model": "openai/gpt-4o-mini",
                                    "temperature": 0.7,
                                    "max_tokens": 150,
                                    "stream": False
                                }
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // when using auth, do client.login(...)

                            async function main() {
                                const response = await client.completion({
                                    messages: [
                                        { role: "system", content: "You are a helpful assistant." },
                                        { role: "user", content: "What is the capital of France?" },
                                        { role: "assistant", content: "The capital of France is Paris." },
                                        { role: "user", content: "What about Italy?" }
                                    ],
                                    generationConfig: {
                                        model: "openai/gpt-4o-mini",
                                        temperature: 0.7,
                                        maxTokens: 150,
                                        stream: false
                                    }
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/completion" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "messages": [
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": "What is the capital of France?"},
                                    {"role": "assistant", "content": "The capital of France is Paris."},
                                    {"role": "user", "content": "What about Italy?"}
                                ],
                                "generation_config": {
                                    "model": "openai/gpt-4o-mini",
                                    "temperature": 0.7,
                                    "max_tokens": 150,
                                    "stream": false
                                }
                                }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def completion(
            messages: list[Message] = Body(
                ...,
                description="List of messages to generate completion for",
                example=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant.",
                    },
                    {
                        "role": "user",
                        "content": "What is the capital of France?",
                    },
                    {
                        "role": "assistant",
                        "content": "The capital of France is Paris.",
                    },
                    {"role": "user", "content": "What about Italy?"},
                ],
            ),
            generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="Configuration for text generation",
                example={
                    "model": "openai/gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 150,
                    "stream": False,
                },
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
            response_model=WrappedCompletionResponse,
        ) -> WrappedLLMChatCompletion:
            """Generate completions for a list of messages.

            This endpoint uses the language model to generate completions for
            the provided messages. The generation process can be customized
            using the generation_config parameter.

            The messages list should contain alternating user and assistant
            messages, with an optional system message at the start. Each
            message should have a 'role' and 'content'.
            """

            return await self.services.retrieval.completion(
                messages=messages,  # type: ignore
                generation_config=generation_config,
            )

        @self.router.post(
            "/retrieval/embedding",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Generate Embeddings",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.retrieval.embedding(
                                text="What is DeepSeek R1?",
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // when using auth, do client.login(...)

                            async function main() {
                                const response = await client.retrieval.embedding({
                                    text: "What is DeepSeek R1?",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.sciphi.ai/v3/retrieval/embedding" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "text": "What is DeepSeek R1?",
                                }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def embedding(
            text: str = Body(
                ...,
                description="Text to generate embeddings for",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedEmbeddingResponse:
            """Generate embeddings for the provided text using the specified
            model.

            This endpoint uses the language model to generate embeddings for
            the provided text. The model parameter specifies the model to use
            for generating embeddings.
            """

            return await self.services.retrieval.embedding(
                text=text,
            )
