import logging
import time
import uuid
from typing import Optional

from r2r.base import (
    GenerationConfig,
    KGSearchSettings,
    KVLoggingSingleton,
    Message,
    R2RException,
    RunManager,
    User,
    VectorSearchSettings,
    manage_run,
    to_async_generator,
)
from r2r.pipes import EvalPipe
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAssistants, R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class RetrievalService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        assistants: R2RAssistants,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )

    @telemetry_event("Search")
    async def search(
        self,
        query: str,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        user: Optional[User] = None,
        *args,
        **kwargs,
    ):
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

            # TODO - Remove these transforms once we have a better way to handle this
            for filter, value in vector_search_settings.search_filters.items():
                if isinstance(value, uuid.UUID):
                    vector_search_settings.search_filters[filter] = str(value)
            if user and not user.is_superuser:
                vector_search_settings.search_filters["user_id"] = str(user.id)

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
                log_id=run_id,
                key="search_latency",
                value=latency,
                is_info_log=False,
            )

            return results.dict()

    @telemetry_event("RAG")
    async def rag(
        self,
        query: str,
        rag_generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        user: Optional[User] = None,
        *args,
        **kwargs,
    ):
        async with manage_run(self.run_manager, "rag_app") as run_id:
            try:
                t0 = time.time()

                # TODO - Remove these transforms once we have a better way to handle this
                for (
                    filter,
                    value,
                ) in vector_search_settings.search_filters.items():
                    if isinstance(value, uuid.UUID):
                        vector_search_settings.search_filters[filter] = str(
                            value
                        )

                if user and not user.is_superuser:
                    vector_search_settings.search_filters["user_id"] = str(
                        user.id
                    )

                if rag_generation_config.stream:
                    t1 = time.time()
                    latency = f"{t1 - t0:.2f}"

                    await self.logging_connection.log(
                        log_id=run_id,
                        key="rag_generation_latency",
                        value=latency,
                        is_info_log=False,
                    )

                    async def stream_response():
                        async with manage_run(self.run_manager, "arag"):
                            async for (
                                chunk
                            ) in await self.pipelines.streaming_rag_pipeline.run(
                                input=to_async_generator([query]),
                                run_manager=self.run_manager,
                                vector_search_settings=vector_search_settings,
                                kg_search_settings=kg_search_settings,
                                rag_generation_config=rag_generation_config,
                                *args,
                                **kwargs,
                            ):
                                yield chunk

                    return stream_response()

                results = await self.pipelines.rag_pipeline.run(
                    input=to_async_generator([query]),
                    run_manager=self.run_manager,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    *args,
                    **kwargs,
                )

                t1 = time.time()
                latency = f"{t1 - t0:.2f}"

                await self.logging_connection.log(
                    log_id=run_id,
                    key="rag_generation_latency",
                    value=latency,
                    is_info_log=False,
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
                        message="Ollama server not reachable or returned an invalid response",
                    )
                raise R2RException(
                    status_code=500, message="Internal Server Error"
                )

    @telemetry_event("RAGChat")
    async def rag_agent(
        self,
        messages: list[Message],
        rag_generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        user: Optional[User] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = False,
        *args,
        **kwargs,
    ):
        async with manage_run(self.run_manager, "rag_agent_app") as run_id:
            try:
                t0 = time.time()

                # Transform UUID filters to strings
                for (
                    filter,
                    value,
                ) in vector_search_settings.search_filters.items():
                    if isinstance(value, uuid.UUID):
                        vector_search_settings.search_filters[filter] = str(
                            value
                        )

                if user and not user.is_superuser:
                    vector_search_settings.search_filters["user_id"] = str(
                        user.id
                    )

                if rag_generation_config.stream:
                    t1 = time.time()
                    latency = f"{t1 - t0:.2f}"

                    await self.logging_connection.log(
                        log_id=run_id,
                        key="rag_agent_generation_latency",
                        value=latency,
                        is_info_log=False,
                    )

                    async def stream_response():
                        async with manage_run(self.run_manager, "arag_agent"):
                            async for (
                                chunk
                            ) in self.assistants.streaming_rag_assistant.arun(
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

                results = await self.assistants.rag_assistant.arun(
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
                    log_id=run_id,
                    key="rag_agent_generation_latency",
                    value=latency,
                    is_info_log=False,
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

    @telemetry_event("Evaluate")
    async def evaluate(
        self,
        query: str,
        context: str,
        completion: str,
        eval_generation_config: Optional[GenerationConfig],
        user: Optional[User] = None,
        *args,
        **kwargs,
    ):
        eval_payload = EvalPipe.EvalPayload(
            query=query,
            context=context,
            completion=completion,
        )
        result = await self.eval_pipeline.run(
            input=to_async_generator([eval_payload]),
            run_manager=self.run_manager,
            eval_generation_config=eval_generation_config,
            *args,
            **kwargs,
        )
        return result
