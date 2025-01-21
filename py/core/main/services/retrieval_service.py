import asyncio
import json
import logging
import time
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from core import R2RRAGAgent, R2RStreamingRAGAgent
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
    Message,
    R2RException,
    SearchSettings,
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

    # ---------------------------------------------------------------------
    # Private method #1: Vector Search (replaces VectorSearchPipe.search)
    # ---------------------------------------------------------------------
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
        query_vector = await self.providers.embedding.async_get_embedding(
            query, purpose=EmbeddingPurpose.QUERY
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
        reranked = await self.providers.embedding.arerank(
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

    # ---------------------------------------------------------------------
    # Private method #2: Graph Search (replaces GraphSearchSearchPipe.search)
    # ---------------------------------------------------------------------
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
        query_embedding = await self.providers.embedding.async_get_embedding(
            query
        )

        base_limit = search_settings.limit
        graph_limits = search_settings.graph_settings.limits or {}

        #
        # 1) Entity search
        #
        entity_limit = graph_limits.get("entities", base_limit)
        entity_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="entities",
            limit=entity_limit,
            query_embedding=query_embedding,
            property_names=["name", "description", "chunk_ids"],
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

        #
        # 2) Relationship search
        #
        rel_limit = graph_limits.get("relationships", base_limit)
        rel_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="relationships",
            limit=rel_limit,
            query_embedding=query_embedding,
            property_names=[
                "subject",
                "predicate",
                "object",
                "description",
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
                        subject=rel.get("subject", ""),
                        predicate=rel.get("predicate", ""),
                        object=rel.get("object", ""),
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

        #
        # 3) Community search
        #
        comm_limit = graph_limits.get("communities", base_limit)
        comm_cursor = self.providers.database.graphs_handler.graph_search(
            query,
            search_type="communities",
            limit=comm_limit,
            query_embedding=query_embedding,
            property_names=[
                "community_id",
                "name",
                "findings",
                "rating",
                "rating_explanation",
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
                        name=comm.get("name", ""),
                        summary=comm.get("summary", ""),
                        rating=comm.get("rating", None),
                        rating_explanation=comm.get("rating_explanation", ""),
                        findings=comm.get("findings", ""),
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
        return await self.providers.embedding.async_get_embedding(text=text)

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
            if rag_generation_config.stream:
                # For streaming, handle separately
                return await self.stream_rag_response(
                    query,
                    rag_generation_config,
                    search_settings,
                    **kwargs,
                )

            # 1) Do the search
            search_results_dict = await self.search(query, search_settings)
            aggregated = AggregateSearchResult.from_dict(search_results_dict)

            # 2) Build context from search results
            #    (You can rename/adjust this as needed)
            context_str = self._build_rag_context(query, aggregated)

            # 3) Prepare your message payload
            #    (Assuming you have some "prompts_handler" for system+task)
            #    If you store your RAG prompt names in config, do something like:
            system_prompt_name = system_prompt_name or "default_system"
            task_prompt_name = task_prompt_name or "rag_context"
            task_prompt_override = kwargs.get("task_prompt_override", None)

            messages = await self.providers.database.prompts_handler.get_message_payload(
                system_prompt_name=system_prompt_name,
                task_prompt_name=task_prompt_name,
                task_inputs={"query": query, "context": context_str},
                task_prompt_override=task_prompt_override,
            )

            # 4) LLM completion
            response = await self.providers.llm.aget_completion(
                messages=messages, generation_config=rag_generation_config
            )

            # 5) Build final RAGResponse
            return RAGResponse(
                completion=response.choices[0].message.content,
                search_results=aggregated,  # let’s store the aggregated search info
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

    def _build_rag_context(
        self,
        query: str,
        results: AggregateSearchResult,
    ) -> str:
        """
        Equivalent to your old RAGPipe._collect_context or a simplified version.
        Combines the chunk search results and graph search results into a single text.
        """
        context = f"Query:\n{query}\n\n"

        # -- Vector/Chunk results
        chunk_results = results.chunk_search_results or []
        if chunk_results:
            context += "Vector Search Results:\n"
            i = 1
            for c in chunk_results:
                context += f"[{i}]: {c.text}\n\n"
                i += 1

        # -- Graph results
        graph_results = results.graph_search_results or []
        if graph_results:
            context += "Knowledge Graph Results:\n"
            j = 1
            for g in graph_results:
                if g.result_type == GraphSearchResultType.ENTITY:
                    context += (
                        f"[{j}]: ENTITY:\n"
                        f"Name: {g.content.name}\n"
                        f"Description: {g.content.description}\n\n"
                    )
                elif g.result_type == GraphSearchResultType.RELATIONSHIP:
                    context += (
                        f"[{j}]: RELATIONSHIP:\n"
                        f"{g.content.subject} - {g.content.predicate} - {g.content.object}\n\n"
                    )
                elif g.result_type == GraphSearchResultType.COMMUNITY:
                    context += (
                        f"[{j}]: COMMUNITY:\n"
                        f"Name: {g.content.name}\n"
                        f"Summary: {g.content.summary}\n\n"
                    )
                j += 1

        return context

    async def stream_rag_response(
        self,
        query,
        rag_generation_config,
        search_settings,
        *args,
        **kwargs,
    ):
        async def stream_response():
            merged_kwargs = {
                "input": to_async_generator([query]),
                "state": None,
                "search_settings": search_settings,
                "rag_generation_config": rag_generation_config,
                **kwargs,
            }

            async for chunk in await self.pipelines.streaming_rag_pipeline.run(
                *args,
                **merged_kwargs,
            ):
                yield chunk

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
    ):
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

            if rag_generation_config.stream:

                async def stream_response():
                    try:
                        agent = R2RStreamingRAGAgent(
                            database_provider=self.providers.database,
                            llm_provider=self.providers.llm,
                            config=self.config.agent,
                            rag_generation_config=rag_generation_config,
                            local_search_method=self.search,
                        )
                        async for chunk in agent.arun(
                            messages=messages,
                            system_instruction=task_prompt_override,
                            search_settings=search_settings,
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
                                            model=self.providers.llm.config.fast_llm
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

                return stream_response()

            agent = R2RRAGAgent(
                database_provider=self.providers.database,
                llm_provider=self.providers.llm,
                config=self.config.agent,
                rag_generation_config=rag_generation_config,
                local_search_method=self.search,
            )

            results = await agent.arun(
                messages=messages,
                system_instruction=task_prompt_override,
                search_settings=search_settings,
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
                prompt = f"Generate a succinct name (3-6 words) for this conversation, given the first input mesasge here = {str(message.to_dict())}"
                conversation_name = (
                    (
                        await self.providers.llm.aget_completion(
                            [{"role": "system", "content": prompt}],
                            GenerationConfig(
                                model=self.providers.llm.config.fast_llm
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
        self, filters: dict[str, Any], options: dict[str, Any]
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

        Returns:
            A list of dicts, where each dict has:
              {
                "document": <DocumentResponse>,
                "chunks": [ <chunk0>, <chunk1>, ... ]
              }
        """
        # 1. Parse and validate filters
        #    We only allow the top-level keys to be: owner_id, document_id, collection_ids
        #    with operators "$eq" or "$in".
        #    If you require "$overlap" for collection_ids, you can add it below.

        # Recognized top-level filter keys
        ALLOWED_FILTERS = {"owner_id", "document_id", "collection_ids"}
        # Recognized operators
        ALLOWED_OPERATORS = {"$eq", "$in", "$overlap"}

        filter_user_ids: Optional[list[UUID]] = None
        filter_document_ids: Optional[list[UUID]] = None
        filter_collection_ids: Optional[list[UUID]] = None

        # We only support a simple top-level structure:
        #   { "owner_id": {"$eq": <uuid>}, "document_id": {"$in": [<uuid>, ...] }, "collection_ids": {"$overlap": [<uuid>, ...] } }
        # If you need more complex logic, you can expand or adapt this parsing.
        for field_key, op_dict in filters.items():
            if field_key not in ALLOWED_FILTERS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported filter field: {field_key}. Allowed: {ALLOWED_FILTERS}",
                )
            if not isinstance(op_dict, dict) or len(op_dict) != 1:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Filter for '{field_key}' must be a dict with exactly one operator "
                        f"from {ALLOWED_OPERATORS}, e.g. {{'{field_key}': {{'$eq': <uuid>}}}}"
                    ),
                )

            (operator, value) = next(iter(op_dict.items()))
            if operator not in ALLOWED_OPERATORS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Unsupported operator for '{field_key}': {operator}. "
                        f"Allowed: {ALLOWED_OPERATORS}"
                    ),
                )

            # Convert value(s) to a list of UUIDs for uniform usage
            if operator in ("$eq", "$overlap"):
                # Single value
                if isinstance(value, str):
                    # Make it a single-element list
                    value_list = [UUID(value)]
                else:
                    # We expected a single str/UUID, but got something else
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Operator '{operator}' for '{field_key}' requires a single string UUID."
                        ),
                    )
            elif operator == "$in":
                # Must be a list of string UUIDs
                if not isinstance(value, list):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Operator '$in' for '{field_key}' must be a list of UUID strings."
                        ),
                    )
                value_list = [UUID(v) for v in value]
            else:
                # Just in case we missed something
                raise HTTPException(
                    status_code=400,
                    detail=f"Operator '{operator}' not supported.",
                )

            # Map them to local filter variables
            if field_key == "owner_id":
                # e.g. user wants { "owner_id": {"$eq": "123e4567-e89b-12d3-a456-426614174000"} }
                filter_user_ids = value_list
            elif field_key == "document_id":
                filter_document_ids = value_list
            elif field_key == "collection_ids":
                filter_collection_ids = value_list

        # 2. Fetch all matching documents. We set offset=0, limit=-1 to get all matches.
        #    The PostgresDocumentsHandler.get_documents_overview method defaults
        #    to ordering by created_at DESC. Adjust if you want a different order.

        matching_docs = await self.providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=-1,
            filter_user_ids=filter_user_ids,
            filter_document_ids=filter_document_ids,
            filter_collection_ids=filter_collection_ids,
            include_summary_embedding=options.get(
                "include_summary_embedding", False
            ),
        )

        if not matching_docs["results"]:
            return []

        # 3. For each document, fetch all associated chunks in ascending chunk order
        #    PostgresChunksHandler.list_document_chunks does:
        #       ORDER BY (metadata->>'chunk_order')::integer

        results = []
        for doc_response in matching_docs["results"]:
            doc_id = doc_response.id
            chunk_data = await self.providers.database.chunks_handler.list_document_chunks(
                document_id=doc_id,
                offset=0,
                limit=-1,  # get all chunks
                include_vectors=False,
            )
            chunks = chunk_data["results"]  # already in ascending chunk_order

            # 4. Build a returned structure that includes doc + chunks
            results.append(
                {
                    "document": doc_response.model_dump(),  # or doc_response.dict() if you prefer
                    "chunks": chunks,
                }
            )

        return results


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
