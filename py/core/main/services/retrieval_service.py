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
    SearchSettings,
    manage_run,
    to_async_generator,
)
from core.base.api.models import (
    CombinedSearchResponse,
    RAGResponse,
    UserResponse,
)
from core.base.logger.base import RunType
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event

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
                search_settings.use_semantic_search
                and search_settings.use_fulltext_search
                and not search_settings.hybrid_search_settings
            ):
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
            print("kwargs = ", kwargs)
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
            messages,
            generation_config,
            *args,
            **kwargs,
        )

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
        conversation_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        message: Optional[Message] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ):
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
            try:
                t0 = time.time()

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

                # Transform UUID filters to strings
                for filter, value in search_settings.filters.items():
                    if isinstance(value, UUID):
                        search_settings.filters[filter] = str(value)

                ids = None

                if not messages:
                    if not message:
                        raise R2RException(
                            status_code=400,
                            message="Message not provided",
                        )
                    # Fetch or create conversation
                    if conversation_id:
                        conversation = (
                            await self.logging_connection.get_conversation(
                                conversation_id, branch_id
                            )
                        )
                        if not conversation:
                            logger.error(
                                f"No conversation found for ID: {conversation_id}"
                            )
                            raise R2RException(
                                status_code=404,
                                message=f"Conversation not found: {conversation_id}",
                            )
                        messages = [conv[1] for conv in conversation] + [  # type: ignore
                            message
                        ]
                        ids = [conv[0] for conv in conversation]
                    else:
                        conversation = (
                            await self.logging_connection.create_conversation()
                        )
                        conversation_id = conversation["id"]

                        parent_id = None
                        if conversation_id and messages:
                            for inner_message in messages[:-1]:
                                parent_id = await self.logging_connection.add_message(
                                    conversation_id,  # Use the stored conversation_id
                                    inner_message,
                                    parent_id,
                                )
                    messages = messages or []

                current_message = messages[-1]  # type: ignore

                # Save the new message to the conversation
                message = await self.logging_connection.add_message(
                    conversation_id,  # type: ignore
                    current_message,  # type: ignore
                    parent_id=str(ids[-2]) if (ids and len(ids) > 1) else None,  # type: ignore
                )
                if message is not None:
                    message_id = message["id"]  # type: ignore

                if rag_generation_config.stream:
                    t1 = time.time()
                    latency = f"{t1 - t0:.2f}"

                    await self.logging_connection.log(
                        run_id=run_id,
                        key="rag_agent_generation_latency",
                        value=latency,
                    )

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
                                *args,
                                **kwargs,
                            ):
                                yield chunk

                    return stream_response()

                results = await self.agents.rag_agent.arun(
                    messages=messages,
                    system_instruction=task_prompt_override,
                    search_settings=search_settings,
                    rag_generation_config=rag_generation_config,
                    include_title_if_available=include_title_if_available,
                    *args,
                    **kwargs,
                )
                await self.logging_connection.add_message(
                    conversation_id=conversation_id,
                    content=Message(**results[-1]),
                    parent_id=message_id,
                )

                t1 = time.time()
                latency = f"{t1 - t0:.2f}"

                await self.logging_connection.log(
                    run_id=run_id,
                    key="rag_agent_generation_latency",
                    value=latency,
                )
                return {
                    "messages": results,
                    "conversation_id": str(
                        conversation_id
                    ),  # Ensure it's a string
                }

            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise HTTPException(
                        status_code=502,
                        detail="Server not reachable or returned an invalid response",
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal Server Error",
                )


class RetrievalServiceAdapter:
    @staticmethod
    def _parse_user_data(user_data):
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid user data format: {user_data}")
        return UserResponse.from_dict(user_data)

    @staticmethod
    def prepare_search_input(
        query: str,
        search_settings: SearchSettings,
        user: UserResponse,
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
        user: UserResponse,
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
        user: UserResponse,
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
