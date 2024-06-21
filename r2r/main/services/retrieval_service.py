import logging
import time
from typing import Optional

from fastapi import HTTPException

from r2r.core import (
    KVLoggingSingleton,
    RunManager,
    manage_run,
    to_async_generator,
)
from r2r.core.abstractions.llm import GenerationConfig
from r2r.pipes import EvalPipe
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import (
    KGSearchSettings,
    R2RPipelines,
    R2RProviders,
    VectorSearchSettings,
)
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class RetrievalService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config, providers, pipelines, run_manager, logging_connection
        )

    @telemetry_event("Search")
    async def search(
        self,
        query: str,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
    ):
        async with manage_run(self.run_manager, "search_app") as run_id:
            t0 = time.time()

            results = await self.pipelines.search_pipeline.run(
                input=to_async_generator([query]),
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                run_manager=self.run_manager,
            )

            t1 = time.time()
            latency = f"{t1-t0:.2f}"

            await self.logging_connection.log(
                log_id=run_id,
                key="search_latency",
                value=latency,
                is_info_log=False,
            )

            return {"results": results.dict()}

    @telemetry_event("RAG")
    async def rag(
        self,
        query: str,
        rag_generation_config: GenerationConfig,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
    ):
        async with manage_run(self.run_manager, "rag_app") as run_id:
            try:
                t0 = time.time()
                if rag_generation_config.stream:
                    t1 = time.time()
                    latency = f"{t1-t0:.2f}"

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
                            ):
                                yield chunk

                    return stream_response()

                results = await self.pipelines.rag_pipeline.run(
                    input=to_async_generator([query]),
                    run_manager=self.run_manager,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                )

                t1 = time.time()
                latency = f"{t1-t0:.2f}"

                await self.logging_connection.log(
                    log_id=run_id,
                    key="rag_generation_latency",
                    value=latency,
                    is_info_log=False,
                )

                return results

            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise HTTPException(
                        status_code=502,
                        detail="Ollama server not reachable or returned an invalid response",
                    )
                raise HTTPException(
                    status_code=500, detail="Internal Server Error"
                )

    @telemetry_event("Evaluate")
    async def evaluate(
        self,
        query: str,
        context: str,
        completion: str,
        eval_generation_config: Optional[GenerationConfig],
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
        )
        return {"results": result}
