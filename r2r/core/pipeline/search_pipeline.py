import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from ..abstractions.search import (
    AggregateSearchResult,
    KGSearchSettings,
    VectorSearchSettings,
)
from ..logging.kv_logger import KVLoggingSingleton
from ..logging.run_manager import RunManager, manage_run
from ..pipes.base_pipe import AsyncPipe, AsyncState
from .base_pipeline import Pipeline, dequeue_requests

logger = logging.getLogger(__name__)


class SearchPipeline(Pipeline):
    """A pipeline for search."""

    pipeline_type: str = "search"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        self.parsing_pipe = None
        self.vector_search_pipeline = None
        self.kg_search_pipeline = None

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        streaming: bool = False,
        run_manager: Optional[RunManager] = None,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        *args: Any,
        **kwargs: Any,
    ):
        self.state = state or AsyncState()

        async with manage_run(run_manager, self.pipeline_type):
            await run_manager.log_run_info(
                key="pipeline_type",
                value=self.pipeline_type,
                is_info_log=True,
            )

            vector_search_queue = Queue()
            kg_queue = Queue()

            async def enqueue_requests():
                async for message in input:
                    if self.vector_search_pipeline:
                        await vector_search_queue.put(message)
                    if self.kg_search_pipeline:
                        await kg_queue.put(message)

                await vector_search_queue.put(None)
                await kg_queue.put(None)

            # Start the document enqueuing process
            enqueue_task = asyncio.create_task(enqueue_requests())

            # Start the embedding and KG pipelines in parallel
            if self.vector_search_pipeline:
                vector_search_task = asyncio.create_task(
                    self.vector_search_pipeline.run(
                        dequeue_requests(vector_search_queue),
                        state,
                        streaming,
                        run_manager,
                        vector_search_settings=vector_search_settings,
                    )
                )

            if self.kg_search_pipeline:
                kg_task = asyncio.create_task(
                    self.kg_search_pipeline.run(
                        dequeue_requests(kg_queue),
                        state,
                        streaming,
                        run_manager,
                        kg_search_settings=kg_search_settings,
                    )
                )

        await enqueue_task

        vector_search_results = (
            await vector_search_task if self.vector_search_pipeline else None
        )
        kg_results = await kg_task if self.kg_search_pipeline else None

        return AggregateSearchResult(
            vector_search_results=vector_search_results,
            kg_search_results=kg_results,
        )

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        kg_pipe: bool = False,
        vector_search_pipe: bool = False,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the SearchPipeline")

        if kg_pipe:
            if not self.kg_search_pipeline:
                self.kg_search_pipeline = Pipeline()
            self.kg_search_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        elif vector_search_pipe:
            if not self.vector_search_pipeline:
                self.vector_search_pipeline = Pipeline()
            self.vector_search_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        else:
            raise ValueError("Pipe must be a vector search or KG pipe")
