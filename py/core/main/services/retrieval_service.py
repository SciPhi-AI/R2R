import json
import logging
import time
from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import (
    CompletionRecord,
    GenerationConfig,
    KGSearchSettings,
    Message,
    MessageType,
    R2RException,
    RunLoggingSingleton,
    RunManager,
    VectorSearchSettings,
    generate_id_from_label,
    manage_run,
    to_async_generator,
)
from core.base.api.models import RAGResponse, SearchResponse
from core.base.api.models.auth.responses import UserResponse
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class RetrievalService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
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
        async with manage_run(self.run_manager, "search_app") as run_id:
            t0 = time.time()

            if (
                kg_search_settings.use_kg_search
                and self.config.kg.provider is None
            ):
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

            results = await self.pipelines.search_pipeline.run(
                input=to_async_generator([query]),
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                run_manager=self.run_manager,
                *args,
                **kwargs,
            )

            t1 = time.time()
            latency = f"{t1 - t0:.2f}"

            await self.logging_connection.log(
                run_id=run_id,
                key="search_latency",
                value=latency,
            )

            return results.dict()

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
        async with manage_run(self.run_manager, "rag_app") as run_id:
            try:
                # TODO - Remove these transforms once we have a better way to handle this
                for (
                    filter,
                    value,
                ) in vector_search_settings.filters.items():
                    if isinstance(value, UUID):
                        vector_search_settings.filters[filter] = str(value)

                completion_start_time = datetime.now()
                message_id = generate_id_from_label(
                    f"{query}-{completion_start_time.isoformat()}"
                )

                completion_record = CompletionRecord(
                    message_id=message_id,
                    message_type=MessageType.ASSISTANT,
                    search_query=query,
                    completion_start_time=completion_start_time,
                )

                if rag_generation_config.stream:
                    return await self.stream_rag_response(
                        query,
                        completion_record,
                        rag_generation_config,
                        vector_search_settings,
                        kg_search_settings,
                        *args,
                        **kwargs,
                    )

                results = await self.pipelines.rag_pipeline.run(
                    input=to_async_generator([query]),
                    run_manager=self.run_manager,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    *args,
                    **kwargs,
                )

                if len(results) == 0:
                    raise R2RException(
                        status_code=404, message="No results found"
                    )
                if len(results) > 1:
                    logger.warning(
                        f"Multiple results found for query: {query}"
                    )

                completion_record.search_results = (
                    results[0].search_results
                    if hasattr(results[0], "search_results")
                    else None
                )
                completion_record.llm_response = (
                    results[0].completion
                    if hasattr(results[0], "completion")
                    else None
                )
                completion_record.completion_end_time = datetime.now()

                await self.logging_connection.log(
                    run_id=run_id,
                    key="completion_record",
                    value=completion_record.to_json(),
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
        completion_record,
        rag_generation_config,
        vector_search_settings,
        kg_search_settings,
        *args,
        **kwargs,
    ):
        async def stream_response():
            async with manage_run(self.run_manager, "rag"):
                async for (
                    chunk
                ) in await self.pipelines.streaming_rag_pipeline.run(
                    input=to_async_generator([query]),
                    run_manager=self.run_manager,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    completion_record=completion_record,
                    *args,
                    **kwargs,
                ):
                    yield chunk

        return stream_response()

    @telemetry_event("Agent")
    async def agent(
        self,
        messages: list[Message],
        rag_generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        *args,
        **kwargs,
    ):
        async with manage_run(self.run_manager, "agent_app") as run_id:
            try:
                t0 = time.time()

                # Transform UUID filters to strings
                for (
                    filter,
                    value,
                ) in vector_search_settings.filters.items():
                    if isinstance(value, UUID):
                        vector_search_settings.filters[filter] = str(value)

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
                            async for (
                                chunk
                            ) in self.agents.streaming_rag_agent.arun(
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
                t1 = time.time()
                latency = f"{t1 - t0:.2f}"

                await self.logging_connection.log(
                    run_id=run_id,
                    key="rag_agent_generation_latency",
                    value=latency,
                )
                return results
            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise R2RException(
                        status_code=502,
                        message="Ollama server not reachable or returned an invalid response",
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
        messages: list[Message],
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        rag_generation_config: GenerationConfig,
        task_prompt_override: Optional[str],
        include_title_if_available: bool,
        user: UserResponse,
    ) -> dict:
        return {
            "messages": [message.to_dict() for message in messages],
            "vector_search_settings": vector_search_settings.to_dict(),
            "kg_search_settings": kg_search_settings.to_dict(),
            "rag_generation_config": rag_generation_config.to_dict(),
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
            "user": user.to_dict(),
        }

    @staticmethod
    def parse_agent_input(data: dict):
        return {
            "messages": [
                Message.from_dict(message) for message in data["messages"]
            ],
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
        }
