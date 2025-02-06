import asyncio
import json
import logging
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from core import (
    R2RRAGAgent,
    R2RStreamingRAGAgent,
    R2RStreamingReasoningRAGAgent,
)
from core.agent.rag import (
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
    format_search_results_for_llm,
    format_search_results_for_stream,
    to_async_generator,
)
from core.base.api.models import RAGResponse, User
from core.telemetry.telemetry_decorator import telemetry_event
from shared.api.models.management.responses import MessageResponse

from ..abstractions import R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


import tiktoken


def tokens_count_for_message(message, encoding):
    """Return the number of tokens used by a single message."""
    tokens_per_message = 3

    num_tokens = 0
    num_tokens += tokens_per_message
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
    """Return the number of tokens used by a list of messages for both user and assistant."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = 0
    for i, message in enumerate(messages):
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
    ) -> AggregateSearchResult:
        """
        Replaces your pipeline-based `SearchPipeline.run(...)` with a single method.
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

        chunk_search_results, kg_results = await asyncio.gather(
            vector_task, graph_task
        )

        # 3) Wrap up in an `AggregateSearchResult`, or your CombinedSearchResponse
        aggregated_result = AggregateSearchResult(
            chunk_search_results=chunk_search_results,
            graph_search_results=kg_results,
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
        """
        Equivalent to your old VectorSearchPipe.search, but simplified:
         • embed query
         • do fulltext, semantic, or hybrid search
         • optional re-rank
         • return list of ChunkSearchResult
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
        results = []
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
                except:
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
                        else None
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
                except:
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
                        else None
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
                except:
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
                        else None
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
        messages: list[dict],
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
        system_prompt_name: Optional[str] = None,
        task_prompt_name: Optional[str] = None,
        *args,
        **kwargs,
    ) -> RAGResponse:
        """
        A simple RAG method that does:
          • vector + KG search
          • build a big 'context' string
          • feed to your system + task prompts
          • call LLM for final answer
        No pipeline classes necessary.
        """
        # Convert any UUID filters to string
        for f, val in list(search_settings.filters.items()):
            if isinstance(val, UUID):
                search_settings.filters[f] = str(val)

        try:
            # Do the search
            search_results_dict = await self.search(query, search_settings)
            aggregated = AggregateSearchResult.from_dict(search_results_dict)

            # Build context from search results
            context_str = format_search_results_for_llm(aggregated)

            # Prepare your message payload
            system_prompt_name = system_prompt_name or "system"
            task_prompt_name = task_prompt_name or "rag"
            task_prompt_override = kwargs.get("task_prompt_override", None)

            messages = await self.providers.database.prompts_handler.get_message_payload(
                system_prompt_name=system_prompt_name,
                task_prompt_name=task_prompt_name,
                task_inputs={"query": query, "context": context_str},
                task_prompt_override=task_prompt_override,
            )

            if rag_generation_config.stream:
                return await self.stream_rag_response(
                    messages=messages,
                    rag_generation_config=rag_generation_config,
                    aggregated_results=aggregated,
                    **kwargs,
                )

            # LLM completion
            response = await self.providers.llm.aget_completion(
                messages=messages, generation_config=rag_generation_config
            )

            # Build final RAGResponse
            return RAGResponse(
                completion=response.choices[0].message.content,
                search_results=aggregated,
            )

        except Exception as e:
            logger.error(f"Error in RAG: {e}")
            if "NoneType" in str(e):
                raise HTTPException(
                    status_code=502,
                    detail="Server not reachable or returned an invalid response",
                )
            raise HTTPException(
                status_code=500,
                detail=f"Internal RAG Error - {str(e)}",
            )

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
                    )
                raise HTTPException(
                    status_code=500, detail=f"Internal RAG Error - {str(e)}"
                )

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
                conversation_response = (
                    await self.providers.database.conversations_handler.create_conversation()
                )
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

            # -- Step 1: parse the filter dict from search_settings
            #    (assuming search_settings.filters is the dict you want to parse)
            filter_user_id, filter_collection_ids = (
                self._parse_user_and_collection_filters(
                    search_settings.filters
                )
            )

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
                        raise
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
                                prompt = f"Generate a succinct name (3-6 words) for this conversation, given the first input mesasge here = {str(message.to_dict())}"
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

            input_tokens = num_tokens_from_messages(results[:-1])
            output_tokens = num_tokens_from_messages([results[-1]])

            await self.providers.database.conversations_handler.add_message(
                conversation_id=conversation_id,
                content=assistant_message,
                parent_id=message_id,
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
            if needs_conversation_name:
                conversation_name = None
                try:
                    prompt = f"Generate a succinct name (3-6 words) for this conversation, given the first input mesasge here = {str(message.to_dict())}"
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
                except Exception as e:
                    pass
                finally:
                    await self.providers.database.conversations_handler.update_conversation(
                        conversation_id=conversation_id,
                        name=conversation_name or "",
                    )

            return {
                "messages": results,
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
                )
            raise HTTPException(
                status_code=500,
                detail=f"Internal Server Error - {str(e)}",
            )

    async def get_context(
        self,
        filters: dict[str, Any],
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Return an ordered list of documents (with minimal overview fields),
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

    def _parse_user_and_collection_filters(
        self,
        filters: dict[str, Any],
    ):
        ### TODO - Come up with smarter way to extract owner / collection ids for non-admin
        filter_starts_with_and = filters.get("$and", None)
        filter_starts_with_or = filters.get("$or", None)
        if filter_starts_with_and:
            try:
                filter_starts_with_and_then_or = filter_starts_with_and[0][
                    "$or"
                ]

                user_id = filter_starts_with_and_then_or[0]["owner_id"]["$eq"]
                collection_ids = filter_starts_with_and_then_or[1][
                    "collection_ids"
                ]["$overlap"]
                return user_id, [str(ele) for ele in collection_ids]
            except Exception as e:
                logger.error(
                    f"Error: {e}.\n\n While"
                    + """ parsing filters: expected format {'$or': [{'owner_id': {'$eq': 'uuid-string-here'}, 'collection_ids': {'$overlap': ['uuid-of-some-collection']}}]}, if you are a superuser then this error can be ignored."""
                )
                return None, []
        elif filter_starts_with_or:
            try:
                user_id = filter_starts_with_or[0]["owner_id"]["$eq"]
                collection_ids = filter_starts_with_or[1]["collection_ids"][
                    "$overlap"
                ]
                return user_id, [str(ele) for ele in collection_ids]
            except Exception as e:
                logger.error(
                    """Error parsing filters: expected format {'$or': [{'owner_id': {'$eq': 'uuid-string-here'}, 'collection_ids': {'$overlap': ['uuid-of-some-collection']}}]}, if you are a superuser then this error can be ignored."""
                )
                return None, []
        else:
            # Admin user
            return None, []

    async def _build_documents_context(
        self,
        filter_user_id: Optional[UUID] = None,
        max_summary_length: int = 128,
        limit: int = 1000,
    ) -> str:
        """
        Fetches documents matching the given filters and returns a formatted string
        enumerating them.
        """
        # We only want up to `limit` documents for brevity
        docs_data = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=limit,
            filter_user_ids=[filter_user_id] if filter_user_id else None,
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
                f"[{i}] Title: {title}, Summary: {doc.summary[0:max_summary_length] + ('...' if len(doc.summary) > max_summary_length else ''),}, Total Tokens: {doc.total_tokens}, ID: {doc.id}"
            )
        return "\n".join(lines)

    async def _build_collections_context(
        self,
        filter_collection_ids: Optional[list[UUID]] = None,
        limit: int = 5,
    ) -> str:
        """
        Fetches collections matching the given filters and returns a formatted string
        enumerating them.
        """
        coll_data = await self.providers.database.collections_handler.get_collections_overview(
            offset=0,
            limit=limit,
            filter_collection_ids=filter_collection_ids,
        )
        colls = coll_data["results"]
        if not colls:
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

        # "dynamic_rag_agent" // "static_rag_agent"

        prompt_name = (
            self.config.agent.agent_dynamic_prompt
            if use_system_context
            else self.config.agent.agent_static_prompt
        )
        if reasoning_agent and (
            "gemini-2.0-flash-thinking-exp-01-21" in model
            or "reasoner" in model  # DeepSeek naming for R1
            or "deepseek-r1" in model.lower()  # Open source naming for R1
        ):
            if not use_system_context:
                raise R2RException(
                    status_code=400,
                    message="Reasoning agent not supported without system context for this model",
                )
            prompt_name = prompt_name + "_prompted_reasoning"

        if use_system_context:
            doc_context_str = await self._build_documents_context(
                filter_user_id=filter_user_id,
            )

            coll_context_str = await self._build_collections_context(
                filter_collection_ids=filter_collection_ids,
            )
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
                raise ValueError(f"Invalid user data format: {user_data}")
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
