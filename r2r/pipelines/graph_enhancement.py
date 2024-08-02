# pipeline for enriching knowledge graphs.

import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from ..base.abstractions.search import (
    AggregateSearchResult,
    KGSearchSettings,
    VectorSearchSettings,
)
from ..base.logging.kv_logger import KVLoggingSingleton
from ..base.logging.run_manager import RunManager, manage_run
from ..base.pipeline.base_pipeline import AsyncPipeline, dequeue_requests
from ..base.pipes.base_pipe import AsyncPipe, AsyncState

logger = logging.getLogger(__name__)

class GraphEnhancementPipeline(AsyncPipeline):
    """A pipeline for search."""

    pipeline_type: str = "other"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = AsyncState(),
        stream: bool = False,
        run_manager: Optional[RunManager] = None,
        log_run_info: bool = True,
        *args: Any,
        **kwargs: Any,
    ):

        self.state = state
        self.run_manager = run_manager 
        

        async with manage_run(self.run_manager, self.pipeline_type):
            if log_run_info:
                await self.run_manager.log_run_info(
                    key="pipeline_type",
                    value=self.pipeline_type,
                    is_info_log=True,
                )
                node_queue = Queue()
                
                async def enqueue_requests():
                    async for message in input:
                        await node_queue.put(message)
                    await node_queue.put(None)

            # Start the document enqueuing process
            enqueue_task = asyncio.create_task(enqueue_requests())

        await enqueue_task

        vector_search_results = (
            await vector_search_task if do_vector_search else None
        )
        kg_results = await kg_task if do_kg else None

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

        # if kg_pipe:
        #     if not self._kg_search_pipeline:
        #         self._kg_search_pipeline = AsyncPipeline()
        #     self._kg_search_pipeline.add_pipe(
        #         pipe, add_upstream_outputs, *args, **kwargs
        #     )
        # elif vector_search_pipe:
        #     if not self._vector_search_pipeline:
        #         self._vector_search_pipeline = AsyncPipeline()
        #     self._vector_search_pipeline.add_pipe(
        #         pipe, add_upstream_outputs, *args, **kwargs
        #     )
        # else:
        #     raise ValueError("Pipe must be a vector search or KG pipe")

        super().add_pipe(pipe, add_upstream_outputs, *args, **kwargs)