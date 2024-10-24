import json
import logging
import time
from typing import Optional
from uuid import UUID

from core import R2RStreamingRAGAgent
from core.base import (
    GenerationConfig,
    KGSearchSettings,
    Message,
    R2RException,
    RunManager,
    RunType,
    VectorSearchSettings,
    manage_run,
    to_async_generator,
)
from core.base.api.models import RAGResponse, SearchResponse, UserResponse
from core.providers.logging.r2r_logging import R2RLoggingProvider
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
        logging_connection: R2RLoggingProvider,
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
    async def search(
        self,
        query: str,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        *args,
        **kwargs,
    ) -> SearchResponse:
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
            t0 = time.time()

            if kg_search_settings.use_kg_search:
                raise R2RException(
                    status_code=400,
                    message="Knowledge Graph search is not enabled in the configuration.",
                )

            if (
                vector_search_settings.use_vector_search
                and self.config.database.provider is None
            ):
                raise R2RException(
                    status_code=400,
                    message="Vector search is not enabled in the configuration.",
                )

            if (
                vector_search_settings.use_vector_search
                and vector_search_settings.use_hybrid_search
                and not vector_search_settings.hybrid_search_settings
            ):
                raise R2RException(
                    status_code=400,
                    message="Hybrid search settings must be specified in the input configuration.",
                )
            # TODO - Remove these transforms once we have a better way to handle this
            for filter, value in vector_search_settings.filters.items():
                if isinstance(value, UUID):
                    vector_search_settings.filters[filter] = str(value)
            merged_kwargs = {
                "input": to_async_generator([query]),
                "state": None,
                "vector_search_settings": vector_search_settings,
                "kg_search_settings": kg_search_settings,
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
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        *args,
        **kwargs,
    ) -> RAGResponse:
        async with manage_run(self.run_manager, RunType.RETRIEVAL) as run_id:
            try:
                # TODO - Remove these transforms once we have a better way to handle this
                for (
                    filter,
                    value,
                ) in vector_search_settings.filters.items():
                    if isinstance(value, UUID):
                        vector_search_settings.filters[filter] = str(value)

                if rag_generation_config.stream:
                    return await self.stream_rag_response(
                        query,
                        rag_generation_config,
                        vector_search_settings,
                        kg_search_settings,
                        *args,
                        **kwargs,
                    )

                merged_kwargs = {
                    "input": to_async_generator([query]),
                    "state": None,
                    "vector_search_settings": vector_search_settings,
                    "kg_search_settings": kg_search_settings,
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
                    raise R2RException(
                        status_code=502,
                        message="Remote server not reachable or returned an invalid response",
                    ) from e
                raise R2RException(
                    status_code=500, message="Internal Server Error"
                ) from e

    async def stream_rag_response(
        self,
        query,
        rag_generation_config,
        vector_search_settings,
        kg_search_settings,
        *args,
        **kwargs,
    ):
        async def stream_response():
            async with manage_run(self.run_manager, "rag"):
                merged_kwargs = {
                    "input": to_async_generator([query]),
                    "state": None,
                    "run_manager": self.run_manager,
                    "vector_search_settings": vector_search_settings,
                    "kg_search_settings": kg_search_settings,
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
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
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
                for filter, value in vector_search_settings.filters.items():
                    if isinstance(value, UUID):
                        vector_search_settings.filters[filter] = str(value)

                ids = None

                if not messages:
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
                        messages = [conv[1] for conv in conversation] + [
                            message
                        ]
                        ids = [conv[0] for conv in conversation]
                    else:
                        conversation_id = (
                            await self.logging_connection.create_conversation()
                        )
                        messages = [message]  # type: ignore
                else:
                    if not conversation_id:
                        conversation_id = (
                            await self.logging_connection.create_conversation()
                        )

                        parent_id = None
                        for inner_message in messages[:-1]:

                            parent_id = (
                                await self.logging_connection.add_message(
                                    conversation_id, inner_message, parent_id
                                )
                            )

                current_message = messages[-1]

                # Save the new message to the conversation
                message_id = await self.logging_connection.add_message(
                    conversation_id,  # type: ignore
                    current_message,  # type: ignore
                    parent_id=str(ids[-2]) if (ids and len(ids) > 1) else None,  # type: ignore
                )

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
                                vector_search_settings=vector_search_settings,
                                kg_search_settings=kg_search_settings,
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
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    include_title_if_available=include_title_if_available,
                    *args,
                    **kwargs,
                )
                await self.logging_connection.add_message(
                    conversation_id,
                    Message(**results[-1]),
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
                    "conversation_id": conversation_id,
                }

            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise R2RException(
                        status_code=502,
                        message="Server not reachable or returned an invalid response",
                    )
                raise R2RException(
                    status_code=500, message="Internal Server Error"
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
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        user: UserResponse,
    ) -> dict:
        return {
            "query": query,
            "vector_search_settings": vector_search_settings.to_dict(),
            "kg_search_settings": kg_search_settings.to_dict(),
            "user": user.to_dict(),
        }

    @staticmethod
    def parse_search_input(data: dict):
        return {
            "query": data["query"],
            "vector_search_settings": VectorSearchSettings.from_dict(
                data["vector_search_settings"]
            ),
            "kg_search_settings": KGSearchSettings.from_dict(
                data["kg_search_settings"]
            ),
            "user": RetrievalServiceAdapter._parse_user_data(data["user"]),
        }

    @staticmethod
    def prepare_rag_input(
        query: str,
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        rag_generation_config: GenerationConfig,
        task_prompt_override: Optional[str],
        user: UserResponse,
    ) -> dict:
        return {
            "query": query,
            "vector_search_settings": vector_search_settings.to_dict(),
            "kg_search_settings": kg_search_settings.to_dict(),
            "rag_generation_config": rag_generation_config.to_dict(),
            "task_prompt_override": task_prompt_override,
            "user": user.to_dict(),
        }

    @staticmethod
    def parse_rag_input(data: dict):
        return {
            "query": data["query"],
            "vector_search_settings": VectorSearchSettings.from_dict(
                data["vector_search_settings"]
            ),
            "kg_search_settings": KGSearchSettings.from_dict(
                data["kg_search_settings"]
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
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        rag_generation_config: GenerationConfig,
        task_prompt_override: Optional[str],
        include_title_if_available: bool,
        user: UserResponse,
        conversation_id: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> dict:
        return {
            "message": message.to_dict(),
            "vector_search_settings": vector_search_settings.to_dict(),
            "kg_search_settings": kg_search_settings.to_dict(),
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
            "vector_search_settings": VectorSearchSettings.from_dict(
                data["vector_search_settings"]
            ),
            "kg_search_settings": KGSearchSettings.from_dict(
                data["kg_search_settings"]
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
