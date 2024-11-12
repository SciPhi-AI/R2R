import asyncio
import textwrap
from typing import Any, Optional
from uuid import UUID

from fastapi import Body, Depends
from fastapi.responses import StreamingResponse

from core.base import (
    GenerationConfig,
    KGSearchSettings,
    Message,
    R2RException,
    VectorSearchSettings,
)
from core.base.api.models import (
    WrappedCompletionResponse,
    WrappedRAGAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
)
from core.base.logger.base import RunType
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from ...services.retrieval_service import RetrievalService
from .base_router import BaseRouterV3


class RetrievalRouterV3(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.RETRIEVAL,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _register_workflows(self):
        pass

    def _select_filters(
        self,
        auth_user: Any,
        search_settings: VectorSearchSettings | KGSearchSettings,
    ) -> dict[str, Any]:
        selected_collections = {
            str(cid) for cid in set(search_settings.selected_collection_ids)
        }

        if auth_user.is_superuser:
            if selected_collections:
                # For superusers, we only filter by selected collections
                filters = {
                    "collection_ids": {"$overlap": list(selected_collections)}
                }
            else:
                filters = {}
        else:
            user_collections = set(auth_user.collection_ids)

            if selected_collections:
                allowed_collections = user_collections.intersection(
                    selected_collections
                )
            else:
                allowed_collections = user_collections
            # for non-superusers, we filter by user_id and selected & allowed collections
            filters = {
                "$or": [
                    {"user_id": {"$eq": auth_user.id}},
                    {
                        "collection_ids": {
                            "$overlap": list(allowed_collections)
                        }
                    },
                ]  # type: ignore
            }

        if search_settings.filters != {}:
            filters = {"$and": [filters, search_settings.filters]}  # type: ignore

        return filters

    def _setup_routes(self):

        @self.router.post(
            "/retrieval/search",
            summary="Search R2R",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.search(
                                query="Who is Aristotle?",
                                vector_search_settings={
                                    "use_vector_search": True,
                                    "filters": {"document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
                                    "search_limit": 20,
                                    "use_hybrid_search": True
                                },
                                kg_search_settings={
                                    "use_kg_search": True,
                                    "kg_search_type": "local",
                                    "kg_search_level": "0",
                                    "generation_config": {
                                        "model": "gpt-4o-mini",
                                        "temperature": 0.7,
                                    },
                                    "local_search_limits": {
                                        "__Entity__": 20,
                                        "__Relationship__": 20,
                                        "__Community__": 20,
                                    },
                                    "max_community_description_length": 65536,
                                    "max_llm_queries_for_global_search": 250
                                }
                            )
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/retrieval/search" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "query": "Who is Aristotle?",
                                "vector_search_settings": {
                                    "use_vector_search": true,
                                    "filters": {"document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
                                    "search_limit": 20,
                                    "use_hybrid_search": true
                                },
                                "kg_search_settings": {
                                    "use_kg_search": true,
                                    "kg_search_type": "local",
                                    "kg_search_level": "0",
                                    "generation_config": {
                                        "model": "gpt-4o-mini",
                                        "temperature": 0.7
                                    },
                                    "local_search_limits": {
                                        "__Entity__": 20,
                                        "__Relationship__": 20,
                                        "__Community__": 20
                                    },
                                    "max_community_description_length": 65536,
                                    "max_llm_queries_for_global_search": 250
                                }
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
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Settings for vector-based search",
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Settings for knowledge graph search",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedSearchResponse:  # type: ignore
            """
            Perform a search query on the vector database and knowledge graph and any other configured search engines.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.

            Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.
            """

            vector_search_settings.filters = self._select_filters(
                auth_user, vector_search_settings
            )

            kg_search_settings.filters = self._select_filters(
                auth_user, kg_search_settings
            )

            results = await self.services["retrieval"].search(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
            )
            return results

        @self.router.post(
            "/retrieval/rag",
            summary="RAG Query",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.rag(
                                query="Who is Aristotle?",
                                vector_search_settings={
                                    "use_vector_search": True,
                                    "filters": {"document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
                                    "search_limit": 20,
                                    "use_hybrid_search": True
                                },
                                kg_search_settings={
                                    "use_kg_search": True,
                                    "kg_search_type": "local",
                                    "kg_search_level": "0",
                                    "generation_config": {
                                        "model": "gpt-4o-mini",
                                        "temperature": 0.7,
                                    }
                                },
                                rag_generation_config={
                                    "stream": False,
                                    "temperature": 0.7,
                                    "max_tokens": 150
                                }
                            )
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/retrieval/rag" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "query": "Who is Aristotle?",
                                "vector_search_settings": {
                                    "use_vector_search": true,
                                    "filters": {"document_id": {"$eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
                                    "search_limit": 20,
                                    "use_hybrid_search": true
                                },
                                "kg_search_settings": {
                                    "use_kg_search": true,
                                    "kg_search_type": "local",
                                    "kg_search_level": "0",
                                    "generation_config": {
                                        "model": "gpt-4o-mini",
                                        "temperature": 0.7
                                    }
                                },
                                "rag_generation_config": {
                                    "stream": false,
                                    "temperature": 0.7,
                                    "max_tokens": 150
                                }
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
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Settings for vector-based search",
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Settings for knowledge graph search",
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="Configuration for RAG generation",
            ),
            task_prompt_override: Optional[str] = Body(
                None,
                description="Optional custom prompt to override default",
            ),
            include_title_if_available: bool = Body(
                False,
                description="Include document titles in responses when available",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRAGResponse:  # type: ignore
            """
            Execute a RAG (Retrieval-Augmented Generation) query.

            This endpoint combines search results with language model generation.
            It supports the same filtering capabilities as the search endpoint,
            allowing for precise control over the retrieved context.

            The generation process can be customized using the `rag_generation_config` parameter.
            """

            vector_search_settings.filters = self._select_filters(
                auth_user, vector_search_settings
            )

            response = await self.services["retrieval"].rag(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                rag_generation_config=rag_generation_config,
                task_prompt_override=task_prompt_override,
                include_title_if_available=include_title_if_available,
            )

            if rag_generation_config.stream:

                async def stream_generator():
                    async for chunk in response:
                        yield chunk
                        await asyncio.sleep(0)

                return StreamingResponse(
                    stream_generator(), media_type="application/json"
                )  # type: ignore
            else:
                return response

        @self.router.post(
            "/retrieval/agent",
            summary="RAG-powered Conversational Agent",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                        from r2r import R2RClient

                        client = R2RClient("http://localhost:7272")
                        # when using auth, do client.login(...)

                        result = client.agent(
                            message={
                                "role": "user",
                                "content": "What were the key contributions of Aristotle to logic and how did they influence later philosophers?"
                            },
                            vector_search_settings={
                                "use_vector_search": True,
                                "filters": {"collection_ids": ["5e157b3a-8469-51db-90d9-52e7d896b49b"]},
                                "search_limit": 20,
                                "use_hybrid_search": True
                            },
                            kg_search_settings={
                                "use_kg_search": True,
                                "kg_search_type": "local",
                                "kg_search_level": "1"
                            },
                            rag_generation_config={
                                "stream": False,
                                "temperature": 0.7,
                                "max_tokens": 1000
                            },
                            include_title_if_available=True,
                            conversation_id="550e8400-e29b-41d4-a716-446655440000"  # Optional for conversation continuity
                        )
                        """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/retrieval/agent" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "message": {
                                    "role": "user",
                                    "content": "What were the key contributions of Aristotle to logic and how did they influence later philosophers?"
                                },
                                "vector_search_settings": {
                                    "use_vector_search": true,
                                    "filters": {"collection_ids": ["5e157b3a-8469-51db-90d9-52e7d896b49b"]},
                                    "search_limit": 20,
                                    "use_hybrid_search": true
                                },
                                "kg_search_settings": {
                                    "use_kg_search": true,
                                    "kg_search_type": "local",
                                    "kg_search_level": "1"
                                },
                                "rag_generation_config": {
                                    "stream": false,
                                    "temperature": 0.7,
                                    "max_tokens": 1000
                                },
                                "include_title_if_available": true,
                                "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
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
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Settings for vector-based search",
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Settings for knowledge graph search",
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="Configuration for RAG generation",
            ),
            task_prompt_override: Optional[str] = Body(
                None,
                description="Optional custom prompt to override default",
            ),
            include_title_if_available: bool = Body(
                True,
                description="Include document titles in responses when available",
            ),
            conversation_id: Optional[UUID] = Body(
                None,
                description="ID of the conversation",
            ),
            branch_id: Optional[UUID] = Body(
                None,
                description="ID of the conversation branch",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRAGAgentResponse:  # type: ignore
            """
            Engage with an intelligent RAG-powered conversational agent for complex information retrieval and analysis.

            This advanced endpoint combines retrieval-augmented generation (RAG) with a conversational AI agent to provide
            detailed, context-aware responses based on your document collection. The agent can:

            - Maintain conversation context across multiple interactions
            - Dynamically search and retrieve relevant information from both vector and knowledge graph sources
            - Break down complex queries into sub-questions for comprehensive answers
            - Cite sources and provide evidence-based responses
            - Handle follow-up questions and clarifications
            - Navigate complex topics with multi-step reasoning

            Key Features:
            - Hybrid search combining vector and knowledge graph approaches
            - Contextual conversation management with conversation_id tracking
            - Customizable generation parameters for response style and length
            - Source document citation with optional title inclusion
            - Streaming support for real-time responses
            - Branch management for exploring different conversation paths

            Common Use Cases:
            - Research assistance and literature review
            - Document analysis and summarization
            - Technical support and troubleshooting
            - Educational Q&A and tutoring
            - Knowledge base exploration

            The agent uses both vector search and knowledge graph capabilities to find and synthesize
            information, providing detailed, factual responses with proper attribution to source documents.
            """

            vector_search_settings.filters = self._select_filters(
                auth_user, vector_search_settings
            )

            kg_search_settings.filters = vector_search_settings.filters
            try:
                response = await self.services["retrieval"].agent(
                    message=message,
                    messages=messages,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    task_prompt_override=task_prompt_override,
                    include_title_if_available=include_title_if_available,
                    conversation_id=(
                        str(conversation_id) if conversation_id else None
                    ),
                    branch_id=str(branch_id) if branch_id else None,
                )

                if rag_generation_config.stream:

                    async def stream_generator():
                        content = ""
                        async for chunk in response:
                            yield chunk
                            content += chunk
                            await asyncio.sleep(0)

                    return StreamingResponse(
                        stream_generator(), media_type="application/json"
                    )  # type: ignore
                else:
                    return response
            except Exception as e:
                raise R2RException(str(e), 500)

        @self.router.post(
            "/retrieval/completion",
            summary="Generate Message Completions",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.completion(
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": "What is the capital of France?"},
                                    {"role": "assistant", "content": "The capital of France is Paris."},
                                    {"role": "user", "content": "What about Italy?"}
                                ],
                                generation_config={
                                    "model": "gpt-4o-mini",
                                    "temperature": 0.7,
                                    "max_tokens": 150,
                                    "stream": False
                                }
                            )
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/retrieval/completion" \\
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
                                    "model": "gpt-4o-mini",
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
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                    "max_tokens": 150,
                    "stream": False,
                },
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
            response_model=WrappedCompletionResponse,
        ):
            """
            Generate completions for a list of messages.

            This endpoint uses the language model to generate completions for the provided messages.
            The generation process can be customized using the generation_config parameter.

            The messages list should contain alternating user and assistant messages, with an optional
            system message at the start. Each message should have a 'role' and 'content'.
            """

            return await self.services["retrieval"].completion(
                messages=messages,
                generation_config=generation_config,
            )
