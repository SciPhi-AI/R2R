import json
import logging
import time
from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from core import R2RStreamingRAGAgent
from core.base import (
    DocumentResponse,
    EmbeddingPurpose,
    GenerationConfig,
    GraphSearchSettings,
    Message,
    R2RException,
    RunManager,
    SearchMode,
    SearchSettings,
    manage_run,
    to_async_generator,
)
from core.base.api.models import CombinedSearchResponse, RAGResponse, User
from core.base.logger.base import RunType
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event
from shared.api.models.management.responses import MessageResponse

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


class RetrievalService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: SqlitePersistentLoggingProvider,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("Search")
    async def search(  # TODO - rename to 'search_chunks'
        self,
        query: str,
        search_settings: SearchSettings = SearchSettings(),
        *args,
        **kwargs,
    ) -> CombinedSearchResponse:
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
            t0 = time.time()

            if (
                search_settings.use_semantic_search
                and self.config.database.provider is None
            ):
                raise R2RException(
                    status_code=400,
                    message="Vector search is not enabled in the configuration.",
                )

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
            # TODO - Remove these transforms once we have a better way to handle this
            for filter, value in search_settings.filters.items():
                if isinstance(value, UUID):
                    search_settings.filters[filter] = str(value)
            merged_kwargs = {
                "input": to_async_generator([query]),
                "state": None,
                "search_settings": search_settings,
                "run_manager": self.run_manager,
                **kwargs,
            }
            results = await self.pipelines.search_pipeline.run(
                *args,
                **merged_kwargs,
            )

            t1 = time.time()
            latency = f"{t1 - t0:.2f}"

            await self.logging_connection.log(
                run_id=run_id,
                key="search_latency",
                value=latency,
            )

            return results.as_dict()

    @telemetry_event("SearchDocuments")
    async def search_documents(
        self,
        query: str,
        settings: SearchSettings,
        query_embedding: Optional[list[float]] = None,
    ) -> list[DocumentResponse]:
        return await self.providers.database.search_documents(
            query_text=query,
            settings=settings,
            query_embedding=query_embedding,
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
        *args,
        **kwargs,
    ) -> RAGResponse:
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
            try:
                # TODO - Remove these transforms once we have a better way to handle this
                for (
                    filter,
                    value,
                ) in search_settings.filters.items():
                    if isinstance(value, UUID):
                        search_settings.filters[filter] = str(value)

                if rag_generation_config.stream:
                    return await self.stream_rag_response(
                        query,
                        rag_generation_config,
                        search_settings,
                        *args,
                        **kwargs,
                    )

                merged_kwargs = {
                    "input": to_async_generator([query]),
                    "state": None,
                    "search_settings": search_settings,
                    "run_manager": self.run_manager,
                    "rag_generation_config": rag_generation_config,
                    **kwargs,
                }

                results = await self.pipelines.rag_pipeline.run(
                    *args,
                    **merged_kwargs,
                )

                if len(results) == 0:
                    raise R2RException(
                        status_code=404, message="No results found"
                    )
                if len(results) > 1:
                    logger.warning(
                        f"Multiple results found for query: {query}"
                    )

                # unpack the first result
                return results[0]

            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise HTTPException(
                        status_code=502,
                        detail="Remote server not reachable or returned an invalid response",
                    ) from e
                raise HTTPException(
                    status_code=500, detail="Internal Server Error"
                ) from e

    async def stream_rag_response(
        self,
        query,
        rag_generation_config,
        search_settings,
        *args,
        **kwargs,
    ):
        async def stream_response():
            async with manage_run(self.run_manager, "rag"):
                merged_kwargs = {
                    "input": to_async_generator([query]),
                    "state": None,
                    "run_manager": self.run_manager,
                    "search_settings": search_settings,
                    "rag_generation_config": rag_generation_config,
                    **kwargs,
                }

                async for (
                    chunk
                ) in await self.pipelines.streaming_rag_pipeline.run(
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
        branch_id: Optional[UUID] = None,
        message: Optional[Message] = None,
        messages: Optional[list[Message]] = None,
    ):
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
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
                            processed_messages.append(
                                Message.from_dict(message)
                            )
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

                if conversation_id:  # Fetch the existing conversation
                    try:
                        conversation = (
                            await self.logging_connection.get_conversation(
                                conversation_id=conversation_id,
                                branch_id=branch_id,
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error fetching conversation: {str(e)}")

                    if conversation is not None:
                        messages_from_conversation: list[Message] = []
                        for message_response in conversation:
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
                        await self.logging_connection.create_conversation()
                    )
                    conversation_id = conversation_response.id

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
                message_response = await self.logging_connection.add_message(
                    conversation_id=conversation_id,
                    content=current_message,
                    parent_id=parent_id,
                )

                message_id = (
                    message_response.id
                    if message_response is not None
                    else None
                )

                if rag_generation_config.stream:

                    async def stream_response():
                        async with manage_run(self.run_manager, "rag_agent"):
                            agent = R2RStreamingRAGAgent(
                                database_provider=self.providers.database,
                                llm_provider=self.providers.llm,
                                config=self.config.agent,
                                search_pipeline=self.pipelines.search_pipeline,
                            )
                            async for chunk in agent.arun(
                                messages=messages,
                                system_instruction=task_prompt_override,
                                search_settings=search_settings,
                                rag_generation_config=rag_generation_config,
                                include_title_if_available=include_title_if_available,
                            ):
                                yield chunk

                    return stream_response()

                results = await self.agents.rag_agent.arun(
                    messages=messages,
                    system_instruction=task_prompt_override,
                    search_settings=search_settings,
                    rag_generation_config=rag_generation_config,
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

                await self.logging_connection.add_message(
                    conversation_id=conversation_id,
                    content=assistant_message,
                    parent_id=message_id,
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
        branch_id: Optional[str] = None,
    ) -> dict:
        return {
            "message": message.to_dict(),
            "search_settings": search_settings.to_dict(),
            "rag_generation_config": rag_generation_config.to_dict(),
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
            "user": user.to_dict(),
            "conversation_id": conversation_id,
            "branch_id": branch_id,
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
            "branch_id": data.get("branch_id"),
        }
