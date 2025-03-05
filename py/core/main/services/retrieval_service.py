# FIXME: Once the agent is properly type annotated, remove the type: ignore comments
import asyncio
import json
import logging
import time
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import tiktoken
from fastapi import HTTPException

from core import (
    R2RRAGAgent,
    R2RStreamingRAGAgent,
    R2RStreamingReasoningRAGAgent,
    SearchResultsCollector,
)
from core.agent.rag import (  # type: ignore
    GeminiXMLToolsStreamingReasoningRAGAgent,
    R2RXMLToolsStreamingReasoningRAGAgent,
)
from core.base import (
    AggregateSearchResult,
    ChunkSearchResult,
    DocumentResponse,
    EmbeddingPurpose,
    GenerationConfig,
    GraphCommunityResult,
    GraphEntityResult,
    GraphRelationshipResult,
    GraphSearchResult,
    GraphSearchResultType,
    IngestionStatus,
    Message,
    R2RException,
    SearchSettings,
    extract_citations,
    format_search_results_for_llm,
    format_search_results_for_stream,
    map_citations_to_collector,
    reassign_citations_in_order,
    select_search_filters,
)
from core.base.api.models import RAGResponse, User
from core.telemetry.telemetry_decorator import telemetry_event
from shared.api.models.management.responses import MessageResponse

from ..abstractions import R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


def convert_nonserializable_objects(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            # Convert key to string if it is a UUID or not already a string.
            new_key = key if isinstance(key, str) else str(key)
            new_obj[new_key] = convert_nonserializable_objects(value)
        return new_obj
    elif isinstance(obj, list):
        return [convert_nonserializable_objects(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_nonserializable_objects(item) for item in obj)
    elif isinstance(obj, set):
        return {convert_nonserializable_objects(item) for item in obj}
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to ISO formatted string
    else:
        return obj


def dump_collector(collector: SearchResultsCollector) -> list[dict[str, Any]]:
    dumped = []
    for source_type, result_obj, _ in collector.get_all_results():
        # Get the dictionary from the result object
        if hasattr(result_obj, "model_dump"):
            result_dict = result_obj.model_dump()
        elif hasattr(result_obj, "dict"):
            result_dict = result_obj.dict()
        else:
            result_dict = (
                result_obj  # Fallback if no conversion method is available
            )

        # Use the recursive conversion on the entire dictionary
        result_dict = convert_nonserializable_objects(result_dict)

        dumped.append(
            {
                "source_type": source_type,
                "result": result_dict,
            }
        )
    return dumped


def tokens_count_for_message(message, encoding):
    """Return the number of tokens used by a single message."""
    num_tokens = 3

    if message.get("function_call"):
        num_tokens += len(encoding.encode(message["function_call"]["name"]))
        num_tokens += len(
            encoding.encode(message["function_call"]["arguments"])
        )
    elif message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            num_tokens += len(encoding.encode(tool_call["function"]["name"]))
            num_tokens += len(
                encoding.encode(tool_call["function"]["arguments"])
            )
    else:
        num_tokens += len(encoding.encode(message["content"]))

    return num_tokens


def num_tokens_from_messages(messages, model="gpt-4o"):
    """Return the number of tokens used by a list of messages for both user and
    assistant."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = 0
    for i, _message in enumerate(messages):
        tokens += tokens_count_for_message(messages[i], encoding)

        tokens += 3  # every reply is primed with assistant
    return tokens


class RetrievalService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        super().__init__(
            config,
            providers,
        )

    @telemetry_event("Search")
    async def search(
        self,
        query: str,
        search_settings: SearchSettings = SearchSettings(),
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """Replaces your pipeline-based `SearchPipeline.run(...)` with a single
        method.

        Does parallel vector + graph search, returning an aggregated result.
        """

        # 1) Start run manager / telemetry
        t0 = time.time()

        # Basic sanity checks:
        if (
            search_settings.use_semantic_search
            and self.config.database.provider is None
        ):
            raise R2RException(
                status_code=400,
                message="Vector search is not enabled in the configuration.",
            )

        # If hybrid search is requested but no config for it
        if (
            (
                search_settings.use_semantic_search
                and search_settings.use_fulltext_search
            )
            or search_settings.use_hybrid_search
        ) and not search_settings.hybrid_settings:
            raise R2RException(
                status_code=400,
                message="Hybrid search settings must be specified in the input configuration.",
            )

        # Convert any UUID filters to string if needed (your old pipeline does that)
        for f, val in list(search_settings.filters.items()):
            if isinstance(val, UUID):
                search_settings.filters[f] = str(val)

        # 2) Vector search & graph search in parallel
        vector_task = asyncio.create_task(
            self._vector_search_logic(query, search_settings)
        )
        graph_task = asyncio.create_task(
            self._graph_search_logic(query, search_settings)
        )

        (
            chunk_search_results,
            graph_search_results_results,
        ) = await asyncio.gather(vector_task, graph_task)

        # 3) Wrap up in an `AggregateSearchResult`, or your CombinedSearchResponse
        aggregated_result = AggregateSearchResult(
            chunk_search_results=chunk_search_results,
            graph_search_results=graph_search_results_results,
        )

        # If your higher-level code returns as_dict(), do that here:
        # Or if you have a CombinedSearchResponse(...) object, fill it out
        response_dict = aggregated_result.as_dict()

        # 4) Telemetry timing
        t1 = time.time()
        latency = f"{t1 - t0:.2f}"
        logger.debug(f"[search] Query='{query}' => took {latency} seconds")

        return response_dict

    # Vector Search
    async def _vector_search_logic(
        self,
        query: str,
        search_settings: SearchSettings,
    ) -> list[ChunkSearchResult]:
        """Equivalent to your old VectorSearchPipe.search, but simplified:

        • embed query • do fulltext, semantic, or hybrid search • optional re-
        rank • return list of ChunkSearchResult
        """
        # If chunk search is disabled, just return empty
        if not search_settings.chunk_settings.enabled:
            return []

        # 1) embed the query
        query_vector = (
            await self.providers.completion_embedding.async_get_embedding(
                query, purpose=EmbeddingPurpose.QUERY
            )
        )

        # 2) Decide which search to run
        if (
            search_settings.use_fulltext_search
            and search_settings.use_semantic_search
        ) or search_settings.use_hybrid_search:
            raw_results = (
                await self.providers.database.chunks_handler.hybrid_search(
                    query_vector=query_vector,
                    query_text=query,
                    search_settings=search_settings,
                )
            )
        elif search_settings.use_fulltext_search:
            raw_results = (
                await self.providers.database.chunks_handler.full_text_search(
                    query_text=query,
                    search_settings=search_settings,
                )
            )
        elif search_settings.use_semantic_search:
            raw_results = (
                await self.providers.database.chunks_handler.semantic_search(
                    query_vector=query_vector,
                    search_settings=search_settings,
                )
            )
        else:
            # If no type of search is requested, we can either return or raise
            raise ValueError(
                "At least one of use_fulltext_search or use_semantic_search must be True"
            )

        # 3) Re-rank if you want a second pass
        reranked = await self.providers.completion_embedding.arerank(
            query=query, results=raw_results, limit=search_settings.limit
        )

        # 4) Possibly add "Document Title" prefix
        final_results = []
        for r in reranked:
            # If requested, or if you always do this:
            if "title" in r.metadata and search_settings.include_metadatas:
                title = r.metadata["title"]
                r.text = f"Document Title: {title}\n\nText: {r.text}"
            # Tag the associated query
            r.metadata["associated_query"] = query
            final_results.append(r)

        return final_results

    # Graph Search
    async def _graph_search_logic(
        self,
        query: str,
        search_settings: SearchSettings,
    ) -> list[GraphSearchResult]:
        """
        Mirrors GraphSearchSearchPipe logic:
          • embed the query
          • search entities, relationships, communities
          • yield GraphSearchResult
        """
        results: list[GraphSearchResult] = []
        # bail early if disabled
        if not search_settings.graph_settings.enabled:
            return results

        # embed query
        query_embedding = (
            await self.providers.completion_embedding.async_get_embedding(
                query
            )
        )

        base_limit = search_settings.limit
        graph_limits = search_settings.graph_settings.limits or {}

        # Entity search
        entity_limit = graph_limits.get("entities", base_limit)
        entity_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="entities",
            limit=entity_limit,
            query_embedding=query_embedding,
            property_names=["name", "description", "id"],
            filters=search_settings.filters,
        )
        async for ent in entity_cursor:
            # Build the GraphSearchResult object
            score = ent.get("similarity_score")
            metadata = ent.get("metadata", {})
            # If there's a possibility that "metadata" is a JSON string, parse it:
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    pass

            # store
            results.append(
                GraphSearchResult(
                    content=GraphEntityResult(
                        name=ent.get("name", ""),
                        description=ent.get("description", ""),
                        id=ent.get("id", None),
                    ),
                    result_type=GraphSearchResultType.ENTITY,
                    score=score if search_settings.include_scores else None,
                    metadata=(
                        {
                            **(metadata or {}),
                            "associated_query": query,
                        }
                        if search_settings.include_metadatas
                        else {}
                    ),
                )
            )

        # Relationship search
        rel_limit = graph_limits.get("relationships", base_limit)
        rel_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="relationships",
            limit=rel_limit,
            query_embedding=query_embedding,
            property_names=[
                "id",
                "subject",
                "predicate",
                "object",
                "description",
                "subject_id",
                "object_id",
            ],
            filters=search_settings.filters,
        )
        async for rel in rel_cursor:
            score = rel.get("similarity_score")
            metadata = rel.get("metadata", {})
            # Possibly parse if it's JSON in a string
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    pass

            results.append(
                GraphSearchResult(
                    content=GraphRelationshipResult(
                        id=rel.get("id", None),
                        subject=rel.get("subject", ""),
                        predicate=rel.get("predicate", ""),
                        object=rel.get("object", ""),
                        subject_id=rel.get("subject_id", None),
                        object_id=rel.get("object_id", None),
                        description=rel.get("description", ""),
                    ),
                    result_type=GraphSearchResultType.RELATIONSHIP,
                    score=score if search_settings.include_scores else None,
                    metadata=(
                        {
                            **(metadata or {}),
                            "associated_query": query,
                        }
                        if search_settings.include_metadatas
                        else {}
                    ),
                )
            )

        # Community search
        comm_limit = graph_limits.get("communities", base_limit)
        comm_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="communities",
            limit=comm_limit,
            query_embedding=query_embedding,
            property_names=[
                "id",
                "name",
                "summary",
            ],
            filters=search_settings.filters,
        )
        async for comm in comm_cursor:
            score = comm.get("similarity_score")
            metadata = comm.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    pass

            results.append(
                GraphSearchResult(
                    content=GraphCommunityResult(
                        id=comm.get("id", None),
                        name=comm.get("name", ""),
                        summary=comm.get("summary", ""),
                    ),
                    result_type=GraphSearchResultType.COMMUNITY,
                    score=score if search_settings.include_scores else None,
                    metadata=(
                        {
                            **(metadata or {}),
                            "associated_query": query,
                        }
                        if search_settings.include_metadatas
                        else {}
                    ),
                )
            )

        return results

    @telemetry_event("SearchDocuments")
    async def search_documents(
        self,
        query: str,
        settings: SearchSettings,
        query_embedding: Optional[list[float]] = None,
    ) -> list[DocumentResponse]:
        return (
            await self.providers.database.documents_handler.search_documents(
                query_text=query,
                settings=settings,
                query_embedding=query_embedding,
            )
        )

    @telemetry_event("Completion")
    async def completion(
        self,
        messages: list[Message],
        generation_config: GenerationConfig,
        *args,
        **kwargs,
    ):
        return await self.providers.llm.aget_completion(
            [message.to_dict() for message in messages],
            generation_config,
            *args,
            **kwargs,
        )

    @telemetry_event("Embedding")
    async def embedding(
        self,
        text: str,
    ):
        return await self.providers.completion_embedding.async_get_embedding(
            text=text
        )

    @telemetry_event("RAG")
    async def rag(
        self,
        query: str,
        rag_generation_config: GenerationConfig,
        search_settings: SearchSettings = SearchSettings(),
        system_prompt_name: str | None = None,
        task_prompt_name: str | None = None,
        *args,
        **kwargs,
    ) -> RAGResponse:
        """
        A simplified RAG method that does:
          1) vector + graph search
          2) build a big 'context' string
          3) feed context + query + optional non-text data to LLM
          4) parse LLM output & return a RAGResponse with text + metadata
        """
        # Convert any UUID filters to string
        for f, val in list(search_settings.filters.items()):
            if isinstance(val, UUID):
                search_settings.filters[f] = str(val)

        try:
            # 1) Do the search
            search_results_dict = await self.search(query, search_settings)
            aggregated_results = AggregateSearchResult.from_dict(
                search_results_dict
            )

            collector = SearchResultsCollector()
            collector.add_aggregate_result(aggregated_results)
            # 2) Build context from search results
            context_str = format_search_results_for_llm(
                aggregated_results, collector
            )

            # 3) Prepare your message payload
            system_prompt_name = system_prompt_name or "system"
            task_prompt_name = task_prompt_name or "rag"
            task_prompt_override = kwargs.get("task_prompt_override", None)

            # In your code, get_message_payload fetches or formats the prompt
            # possibly substituting {query} and {context} into a template
            messages = await self.providers.database.prompts_handler.get_message_payload(
                system_prompt_name=system_prompt_name,
                task_prompt_name=task_prompt_name,
                task_inputs={"query": query, "context": context_str},
                task_prompt_override=task_prompt_override,
            )

            # 4) If streaming, handle that
            if rag_generation_config.stream:
                return await self.stream_rag_response(
                    messages=messages,
                    rag_generation_config=rag_generation_config,
                    aggregated_results=aggregated_results,
                    **kwargs,
                )

            # 5) Non-streaming: call the LLM with your modalities
            #    `aget_completion` below will forward the "modalities" key
            #    to your underlying _execute_task call
            response = await self.providers.llm.aget_completion(
                messages=messages,
                generation_config=rag_generation_config,
            )

            # 1) original LLM text
            llm_text_response = response.choices[0].message.content

            # 2) detect citations as the LLM wrote them
            raw_citations = extract_citations(llm_text_response or "")

            # 3) re-map them in ascending order => new_text has sequential references [1], [2], ...
            re_labeled_text, new_citations = reassign_citations_in_order(
                text=llm_text_response or "", citations=raw_citations
            )

            collector = SearchResultsCollector()
            collector.add_aggregate_result(aggregated_results)

            # 4) map to sources
            mapped_citations = map_citations_to_collector(
                new_citations, collector
            )

            metadata = response.dict()
            metadata["choices"][0]["message"].pop(
                "content", None
            )  # remove content from metadata

            # 5) Build final RAG response
            #    If you want to return the newly-labeled text to the user, do so:
            return RAGResponse(
                generated_answer=re_labeled_text,  # or "generated_answer" if you prefer
                search_results=aggregated_results,
                citations=mapped_citations,
                metadata=metadata,
                completion=re_labeled_text,
            )

        except Exception as e:
            logger.error(f"Error in RAG: {e}")
            if "NoneType" in str(e):
                raise HTTPException(
                    status_code=502,
                    detail="Server not reachable or returned an invalid response",
                ) from e
            raise HTTPException(
                status_code=500,
                detail=f"Internal RAG Error - {str(e)}",
            ) from e

    async def stream_rag_response(
        self,
        messages,
        rag_generation_config,
        aggregated_results,
        **kwargs,
    ):
        # FIXME: We need to yield aggregated_results as well
        async def stream_response():
            try:
                yield format_search_results_for_stream(aggregated_results)
                yield "\n<completion>\n"
                async for chunk in self.providers.llm.aget_completion_stream(
                    messages=messages, generation_config=rag_generation_config
                ):
                    yield chunk.choices[0].delta.content or ""
                yield "</completion>"
            except Exception as e:
                logger.error(f"Error in streaming RAG: {e}")
                if "NoneType" in str(e):
                    raise HTTPException(
                        status_code=502,
                        detail="Server not reachable or returned an invalid response",
                    ) from e
                raise HTTPException(
                    status_code=500, detail=f"Internal RAG Error - {str(e)}"
                ) from e

        return stream_response()

    @telemetry_event("Agent")
    async def agent(
        self,
        rag_generation_config: GenerationConfig,
        search_settings: SearchSettings = SearchSettings(),
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        conversation_id: Optional[UUID] = None,
        message: Optional[Message] = None,
        messages: Optional[list[Message]] = None,
        use_system_context: bool = False,
        max_tool_context_length: int = 32_768,
        override_tools: Optional[list[dict[str, Any]]] = None,
        reasoning_agent: bool = False,
        auth_user: Optional[Any] = None,
    ):
        if reasoning_agent and not rag_generation_config.stream:
            raise R2RException(
                status_code=400,
                message="Currently, the reasoning agent can only be used with `stream=True`.",
            )
        try:
            if message and messages:
                raise R2RException(
                    status_code=400,
                    message="Only one of message or messages should be provided",
                )

            if not message and not messages:
                raise R2RException(
                    status_code=400,
                    message="Either message or messages should be provided",
                )

            # Ensure 'message' is a Message instance
            if message and not isinstance(message, Message):
                if isinstance(message, dict):
                    message = Message.from_dict(message)
                else:
                    raise R2RException(
                        status_code=400,
                        message="""
                            Invalid message format. The expected format contains:
                                role: MessageType | 'system' | 'user' | 'assistant' | 'function'
                                content: Optional[str]
                                name: Optional[str]
                                function_call: Optional[dict[str, Any]]
                                tool_calls: Optional[list[dict[str, Any]]]
                                """,
                    )

            # Ensure 'messages' is a list of Message instances
            if messages:
                processed_messages = []
                for message in messages:
                    if isinstance(message, Message):
                        processed_messages.append(message)
                    elif hasattr(message, "dict"):
                        processed_messages.append(
                            Message.from_dict(message.dict())
                        )
                    elif isinstance(message, dict):
                        processed_messages.append(Message.from_dict(message))
                    else:
                        processed_messages.append(
                            Message.from_dict(str(message))
                        )
                messages = processed_messages
            else:
                messages = []

            # Transform UUID filters to strings
            for filter_key, value in search_settings.filters.items():
                if isinstance(value, UUID):
                    search_settings.filters[filter_key] = str(value)

            ids = []
            needs_conversation_name = False
            if conversation_id:  # Fetch the existing conversation
                try:
                    conversation_messages = await self.providers.database.conversations_handler.get_conversation(
                        conversation_id=conversation_id,
                    )
                    needs_conversation_name = len(conversation_messages) == 0
                except Exception as e:
                    logger.error(f"Error fetching conversation: {str(e)}")

                if conversation_messages is not None:
                    messages_from_conversation: list[Message] = []
                    for message_response in conversation_messages:
                        if isinstance(message_response, MessageResponse):
                            messages_from_conversation.append(
                                message_response.message
                            )
                            ids.append(message_response.id)
                        else:
                            logger.warning(
                                f"Unexpected type in conversation found: {type(message_response)}\n{message_response}"
                            )
                    messages = messages_from_conversation + messages
            else:  # Create new conversation
                conversation_response = await self.providers.database.conversations_handler.create_conversation()
                conversation_id = conversation_response.id
                needs_conversation_name = True

            if message:
                messages.append(message)

            if not messages:
                raise R2RException(
                    status_code=400,
                    message="No messages to process",
                )

            current_message = messages[-1]
            logger.info(
                f"Running the agent with conversation_id = {conversation_id} and message = {current_message}"
            )
            # Save the new message to the conversation
            parent_id = ids[-1] if ids else None
            message_response = await self.providers.database.conversations_handler.add_message(
                conversation_id=conversation_id,
                content=current_message,
                parent_id=parent_id,
            )

            message_id = (
                message_response.id if message_response is not None else None
            )

            if auth_user is not None:
                search_settings.filters = select_search_filters(
                    auth_user, search_settings
                )

            filter_user_id = (
                auth_user.id
                if auth_user and not auth_user.is_superuser
                else None
            )
            filter_collection_ids = []

            if "collection_ids" in search_settings.filters:
                overlap_obj = search_settings.filters["collection_ids"]
                if "$overlap" in overlap_obj:
                    filter_collection_ids = list(overlap_obj["$overlap"])
            if "$or" in search_settings.filters:
                for item in search_settings.filters["$or"]:
                    if (
                        "collection_ids" in item
                        and "$overlap" in item["collection_ids"]
                    ):
                        filter_collection_ids = list(
                            item["collection_ids"]["$overlap"]
                        )
            elif "$and" in search_settings.filters:
                for item in search_settings.filters["$and"]:
                    if "$or" in item:
                        for or_item in item["$or"]:
                            if (
                                "collection_ids" in or_item
                                and "$overlap" in or_item["collection_ids"]
                            ):
                                filter_collection_ids = [
                                    str(cid)
                                    for cid in or_item["collection_ids"][
                                        "$overlap"
                                    ]
                                ]

            system_instruction = None

            if use_system_context and task_prompt_override:
                raise R2RException(
                    status_code=400,
                    message="Both use_system_context and task_prompt_override cannot be True at the same time",
                )

            # STEP 1: Determine the final system prompt content
            if task_prompt_override:
                if reasoning_agent:
                    raise R2RException(
                        status_code=400,
                        message="Reasoning agent not supported with task prompt override",
                    )

                system_instruction = task_prompt_override
            else:
                system_instruction = (
                    await self._build_aware_system_instruction(
                        max_tool_context_length=max_tool_context_length,
                        filter_user_id=filter_user_id,
                        filter_collection_ids=filter_collection_ids,
                        model=rag_generation_config.model,
                        use_system_context=use_system_context,
                        reasoning_agent=reasoning_agent,
                    )
                )

            agent_config = deepcopy(self.config.agent)
            agent_config.tools = override_tools or agent_config.tools

            if rag_generation_config.stream:

                async def stream_response():
                    try:
                        if not reasoning_agent:
                            agent = R2RStreamingRAGAgent(
                                database_provider=self.providers.database,
                                llm_provider=self.providers.llm,
                                config=agent_config,
                                search_settings=search_settings,
                                rag_generation_config=rag_generation_config,
                                max_tool_context_length=max_tool_context_length,
                                local_search_method=self.search,
                                content_method=self.get_context,
                            )
                        else:
                            if (
                                "gemini-2.0-flash-thinking-exp-01-21"
                                in rag_generation_config.model
                            ):
                                agent_config.include_tools = False
                                agent = GeminiXMLToolsStreamingReasoningRAGAgent(
                                    database_provider=self.providers.database,
                                    llm_provider=self.providers.llm,
                                    config=agent_config,
                                    search_settings=search_settings,
                                    rag_generation_config=rag_generation_config,
                                    max_tool_context_length=max_tool_context_length,
                                    local_search_method=self.search,
                                    content_method=self.get_context,
                                )
                            elif (
                                "reasoner" in rag_generation_config.model
                                or "deepseek-r1"
                                in rag_generation_config.model.lower()
                            ):
                                agent_config.include_tools = False
                                agent = R2RXMLToolsStreamingReasoningRAGAgent(
                                    database_provider=self.providers.database,
                                    llm_provider=self.providers.llm,
                                    config=agent_config,
                                    search_settings=search_settings,
                                    rag_generation_config=rag_generation_config,
                                    max_tool_context_length=max_tool_context_length,
                                    local_search_method=self.search,
                                    content_method=self.get_context,
                                )
                            elif (
                                "claude-3-5-sonnet-20241022"
                                in rag_generation_config.model
                                or "gpt-4o" in rag_generation_config.model
                                or "o3-mini" in rag_generation_config.model
                            ):
                                agent = R2RStreamingReasoningRAGAgent(
                                    database_provider=self.providers.database,
                                    llm_provider=self.providers.llm,
                                    config=agent_config,
                                    search_settings=search_settings,
                                    rag_generation_config=rag_generation_config,
                                    max_tool_context_length=max_tool_context_length,
                                    local_search_method=self.search,
                                    content_method=self.get_context,
                                )
                            else:
                                raise R2RException(
                                    status_code=400,
                                    message=f"Reasoning agent not supported for this model {rag_generation_config.model}",
                                )

                        async for chunk in agent.arun(
                            messages=messages,
                            system_instruction=system_instruction,
                            include_title_if_available=include_title_if_available,
                        ):
                            yield chunk
                    except Exception as e:
                        logger.error(f"Error streaming agent output: {e}")
                        raise e
                    finally:
                        msgs = [
                            msg.to_dict()
                            for msg in agent.conversation.messages
                        ]
                        input_tokens = num_tokens_from_messages(msgs[:-1])
                        output_tokens = num_tokens_from_messages([msgs[-1]])
                        await self.providers.database.conversations_handler.add_message(
                            conversation_id=conversation_id,
                            content=agent.conversation.messages[-1],
                            parent_id=message_id,
                            metadata={
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                            },
                        )
                        # TODO  - no copy pasta!
                        if needs_conversation_name:
                            try:
                                prompt = f"Generate a succinct name (3-6 words) for this conversation, given the first input message here = {str(message.to_dict())}"
                                conversation_name = (
                                    (
                                        await self.providers.llm.aget_completion(
                                            [
                                                {
                                                    "role": "system",
                                                    "content": prompt,
                                                }
                                            ],
                                            GenerationConfig(
                                                model=self.config.app.fast_llm
                                            ),
                                        )
                                    )
                                    .choices[0]
                                    .message.content
                                )
                                await self.providers.database.conversations_handler.update_conversation(
                                    conversation_id=conversation_id,
                                    name=conversation_name,
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error generating conversation name: {e}"
                                )

                return stream_response()

            agent = R2RRAGAgent(
                database_provider=self.providers.database,
                llm_provider=self.providers.llm,
                config=agent_config,
                search_settings=search_settings,
                rag_generation_config=rag_generation_config,
                max_tool_context_length=max_tool_context_length,
                local_search_method=self.search,
                content_method=self.get_context,
            )

            results = await agent.arun(
                messages=messages,
                system_instruction=system_instruction,
                include_title_if_available=include_title_if_available,
            )

            # Save the assistant's reply to the conversation
            if isinstance(results[-1], dict):
                assistant_message = Message(**results[-1])
            elif isinstance(results[-1], Message):
                assistant_message = results[-1]
            else:
                assistant_message = Message(
                    role="assistant", content=str(results[-1])
                )

            if hasattr(agent, "search_results_collector"):
                collector = agent.search_results_collector
            else:
                collector = SearchResultsCollector()  # or fallback if needed

            # Suppose your final assistant text is:
            raw_text = assistant_message.content or ""

            # Step (1) - detect citations [2], [8], etc.
            raw_citations = extract_citations(raw_text)

            # Step (2) - re-map them in ascending order => new_text has [1], [2], [3], ...
            re_labeled_text, new_citations = reassign_citations_in_order(
                raw_text, raw_citations
            )

            # Step (3) - map them to the aggregator-based search results
            mapped_citations = map_citations_to_collector(
                new_citations, agent.search_results_collector
            )

            # Overwrite final text in the conversation
            assistant_message.content = re_labeled_text

            # Then store the mapped citations if you wish:
            citations_data = [c.model_dump() for c in mapped_citations]

            # 4) Persist everything in the conversation DB
            await self.providers.database.conversations_handler.add_message(
                conversation_id=conversation_id,
                content=assistant_message,
                parent_id=message_id,
                metadata={
                    "citations": citations_data,
                    # You can also store the entire collector or just dump the underlying results
                    "aggregated_search_result": json.dumps(
                        dump_collector(collector)
                    ),
                },
            )

            if needs_conversation_name:
                conversation_name = None
                try:
                    if message:
                        prompt = f"Generate a succinct name (3-6 words) for this conversation, given the first input message here = {str(message.to_dict())}"
                    else:
                        prompt = "Generate a succinct name (3-6 words) for this conversation"
                    conversation_name = (
                        (
                            await self.providers.llm.aget_completion(
                                [{"role": "system", "content": prompt}],
                                GenerationConfig(
                                    model=self.config.app.fast_llm
                                ),
                            )
                        )
                        .choices[0]
                        .message.content
                    )
                except Exception:
                    pass
                finally:
                    await self.providers.database.conversations_handler.update_conversation(
                        conversation_id=conversation_id,
                        name=conversation_name or "",
                    )

            return {
                "messages": [
                    Message(
                        role="assistant",
                        content=assistant_message.content,
                        metadata={
                            "citations": citations_data,
                            # You can also store the entire collector or just dump the underlying results
                            "aggregated_search_result": json.dumps(
                                dump_collector(collector)
                            ),
                        },
                    )
                ],
                "conversation_id": str(
                    conversation_id
                ),  # Ensure it's a string
            }

        except Exception as e:
            logger.error(f"Error in agent response: {str(e)}")
            if "NoneType" in str(e):
                raise HTTPException(
                    status_code=502,
                    detail="Server not reachable or returned an invalid response",
                ) from e
            raise HTTPException(
                status_code=500,
                detail=f"Internal Server Error - {str(e)}",
            ) from e

    async def get_context(
        self,
        filters: dict[str, Any],
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return an ordered list of documents (with minimal overview fields),
        plus all associated chunks in ascending chunk order.

        Only the filters: owner_id, collection_ids, and document_id
        are supported. If any other filter or operator is passed in,
        we raise an error.

        Args:
            filters: A dictionary describing the allowed filters
                     (owner_id, collection_ids, document_id).
            options: A dictionary with extra options, e.g. include_summary_embedding
                     or any custom flags for additional logic.

        Returns:
            A list of dicts, where each dict has:
              {
                "document": <DocumentResponse>,
                "chunks": [ <chunk0>, <chunk1>, ... ]
              }
        """
        # 2. Fetch matching documents
        matching_docs = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=-1,
            filters=filters,
            include_summary_embedding=options.get(
                "include_summary_embedding", False
            ),
        )

        if not matching_docs["results"]:
            return []

        # 3. For each document, fetch associated chunks in ascending chunk order
        results = []
        for doc_response in matching_docs["results"]:
            doc_id = doc_response.id
            chunk_data = await self.providers.database.chunks_handler.list_document_chunks(
                document_id=doc_id,
                offset=0,
                limit=-1,  # get all chunks
                include_vectors=False,
            )
            chunks = chunk_data["results"]  # already sorted by chunk_order

            # 4. Build a returned structure that includes doc + chunks
            results.append(
                {
                    "document": doc_response.model_dump(),
                    # or doc_response.dict() or doc_response.model_dump()
                    "chunks": chunks,
                }
            )

        return results

    async def _build_documents_context(
        self,
        filter_user_id: Optional[UUID] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
        max_summary_length: int = 128,
        limit: int = 1000,
    ) -> str:
        """Fetches documents matching the given filters and returns a formatted
        string enumerating them."""
        filters = {}

        if filter_collection_ids and len(filter_collection_ids) > 0:
            # Use the collection filter with $overlap operator
            filters["collection_ids"] = {"$overlap": filter_collection_ids}

        # We only want up to `limit` documents for brevity
        docs_data = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=limit,
            filter_user_ids=[filter_user_id] if filter_user_id else None,
            filter_collection_ids=filter_collection_ids,
            include_summary_embedding=False,
        )

        docs = docs_data["results"]
        if not docs:
            return "No documents found."

        lines = []
        for i, doc in enumerate(docs, start=1):
            if (
                not doc.summary
                or doc.ingestion_status != IngestionStatus.SUCCESS
            ):
                lines.append(
                    f"[{i}] Title: {doc.title}, Summary: (Summary not available), Status:{doc.ingestion_status} ID: {doc.id}"
                )
                continue

            # Build a line referencing the doc
            title = doc.title or "(Untitled Document)"
            lines.append(
                f"[{i}] Title: {title}, Summary: {(doc.summary[:max_summary_length] + ('...' if len(doc.summary) > max_summary_length else ''),)}, Total Tokens: {doc.total_tokens}, ID: {doc.id}"
            )
        return "\n".join(lines)

    async def _build_collections_context(
        self,
        filter_collection_ids: Optional[list[UUID]] = None,
        limit: int = 5,
    ) -> str:
        """Fetches collections matching the given filters and returns a
        formatted string enumerating them."""
        coll_data = await self.providers.database.collections_handler.get_collections_overview(
            offset=0,
            limit=limit,
            filter_collection_ids=filter_collection_ids,
        )
        colls = coll_data["results"] if isinstance(coll_data, dict) else []
        if not colls or not isinstance(colls, list):
            return "No collections found."

        lines = []
        for i, c in enumerate(colls, start=1):
            name = c.name or "(Unnamed Collection)"
            cid = str(c.id)
            doc_count = c.document_count or 0
            lines.append(f"[{i}] Name: {name} (ID: {cid}, docs: {doc_count})")
        return "\n".join(lines)

    async def _build_aware_system_instruction(
        self,
        max_tool_context_length: int = 10_000,
        filter_user_id: Optional[UUID] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
        model: Optional[str] = None,
        use_system_context: bool = False,
        reasoning_agent: bool = False,
    ) -> str:
        """
        High-level method that:
          1) builds the documents context
          2) builds the collections context
          3) loads the new `dynamic_reasoning_rag_agent` prompt
        """
        date_str = str(datetime.now().isoformat()).split("T")[0]

        prompt_name = (
            self.config.agent.agent_dynamic_prompt
            if use_system_context or reasoning_agent
            else self.config.agent.agent_static_prompt
        )

        # TODO: This should just be enforced in the config
        if model is None:
            raise R2RException(
                status_code=400,
                message="Model not provided for system instruction",
            )

        if ("gemini" in model or "claude" in model) and reasoning_agent:
            prompt_name = f"{prompt_name}_prompted_reasoning"

        if use_system_context or reasoning_agent:
            doc_context_str = await self._build_documents_context(
                filter_user_id=filter_user_id,
                filter_collection_ids=filter_collection_ids,
            )

            coll_context_str = await self._build_collections_context(
                filter_collection_ids=filter_collection_ids,
            )
            logger.debug(f"Loading prompt {prompt_name}")
            # Now fetch the prompt from the database prompts handler
            # This relies on your "rag_agent_extended" existing with
            # placeholders: date, document_context, collection_context
            system_prompt = await self.providers.database.prompts_handler.get_cached_prompt(
                # We use custom tooling and a custom agent to handle gemini models
                prompt_name,
                inputs={
                    "date": date_str,
                    "max_tool_context_length": max_tool_context_length,
                    "document_context": doc_context_str,
                    "collection_context": coll_context_str,
                },
            )
        else:
            system_prompt = await self.providers.database.prompts_handler.get_cached_prompt(
                prompt_name,
                inputs={
                    "date": date_str,
                },
            )
        logger.info(f"Running agent with system prompt = {system_prompt}")
        return system_prompt


class RetrievalServiceAdapter:
    @staticmethod
    def _parse_user_data(user_data):
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except json.JSONDecodeError:
                raise ValueError(
                    f"Invalid user data format: {user_data}"
                ) from None
        return User.from_dict(user_data)

    @staticmethod
    def prepare_search_input(
        query: str,
        search_settings: SearchSettings,
        user: User,
    ) -> dict:
        return {
            "query": query,
            "search_settings": search_settings.to_dict(),
            "user": user.to_dict(),
        }

    @staticmethod
    def parse_search_input(data: dict):
        return {
            "query": data["query"],
            "search_settings": SearchSettings.from_dict(
                data["search_settings"]
            ),
            "user": RetrievalServiceAdapter._parse_user_data(data["user"]),
        }

    @staticmethod
    def prepare_rag_input(
        query: str,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        task_prompt_override: Optional[str],
        user: User,
    ) -> dict:
        return {
            "query": query,
            "search_settings": search_settings.to_dict(),
            "rag_generation_config": rag_generation_config.to_dict(),
            "task_prompt_override": task_prompt_override,
            "user": user.to_dict(),
        }

    @staticmethod
    def parse_rag_input(data: dict):
        return {
            "query": data["query"],
            "search_settings": SearchSettings.from_dict(
                data["search_settings"]
            ),
            "rag_generation_config": GenerationConfig.from_dict(
                data["rag_generation_config"]
            ),
            "task_prompt_override": data["task_prompt_override"],
            "user": RetrievalServiceAdapter._parse_user_data(data["user"]),
        }

    @staticmethod
    def prepare_agent_input(
        message: Message,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        task_prompt_override: Optional[str],
        include_title_if_available: bool,
        user: User,
        conversation_id: Optional[str] = None,
    ) -> dict:
        return {
            "message": message.to_dict(),
            "search_settings": search_settings.to_dict(),
            "rag_generation_config": rag_generation_config.to_dict(),
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
            "user": user.to_dict(),
            "conversation_id": conversation_id,
        }

    @staticmethod
    def parse_agent_input(data: dict):
        return {
            "message": Message.from_dict(data["message"]),
            "search_settings": SearchSettings.from_dict(
                data["search_settings"]
            ),
            "rag_generation_config": GenerationConfig.from_dict(
                data["rag_generation_config"]
            ),
            "task_prompt_override": data["task_prompt_override"],
            "include_title_if_available": data["include_title_if_available"],
            "user": RetrievalServiceAdapter._parse_user_data(data["user"]),
            "conversation_id": data.get("conversation_id"),
        }
