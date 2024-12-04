import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from ..base.abstractions import (
    AggregateSearchResult,
    GraphSearchSettings,
    SearchSettings,
)
from ..base.logger.run_manager import RunManager, manage_run
from ..base.pipeline.base_pipeline import AsyncPipeline, dequeue_requests
from ..base.pipes.base_pipe import AsyncPipe, AsyncState
from ..providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class SearchPipeline(AsyncPipeline):
    """A pipeline for search."""

    def __init__(
        self,
        logging_provider: SqlitePersistentLoggingProvider,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(logging_provider, run_manager)
        self._parsing_pipe: Optional[AsyncPipe] = None
        self._vector_search_pipeline: Optional[AsyncPipeline] = None
        self._kg_search_pipeline: Optional[AsyncPipeline] = None

    async def run(  # type: ignore
        self,
        input: Any,
        state: Optional[AsyncState],
        stream: bool = False,
        run_manager: Optional[RunManager] = None,
        search_settings: SearchSettings = SearchSettings(),
        *args: Any,
        **kwargs: Any,
    ):
        request_state = state or AsyncState()

        run_manager = run_manager or self.run_manager
        async with manage_run(run_manager):
            vector_search_queue: Queue[str] = Queue()
            kg_queue: Queue[str] = Queue()

            async def enqueue_requests():
                async for message in input:
                    await vector_search_queue.put(message)
                    await kg_queue.put(message)

                await vector_search_queue.put(None)
                await kg_queue.put(None)

            # Start the document enqueuing process
            enqueue_task = asyncio.create_task(enqueue_requests())

            # Start the embedding and KG pipelines in parallel
            vector_search_task = asyncio.create_task(
                self._vector_search_pipeline.run(
                    dequeue_requests(vector_search_queue),
                    request_state,
                    stream,
                    run_manager,
                    search_settings=search_settings,
                    *args,
                    **kwargs,
                )
            )
            kg_task = asyncio.create_task(
                self._kg_search_pipeline.run(
                    dequeue_requests(kg_queue),
                    request_state,
                    stream,
                    run_manager,
                    search_settings=search_settings,
                    *args,
                    **kwargs,
                )
            )

        await enqueue_task

        chunk_search_results = await vector_search_task
        kg_results = await kg_task

        return AggregateSearchResult(
            chunk_search_results=chunk_search_results,
            graph_search_results=kg_results,
        )

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        kg_search_pipe: bool = False,
        vector_search_pipe: bool = False,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the SearchPipeline")

        if kg_search_pipe:
            if not self._kg_search_pipeline:
                self._kg_search_pipeline = AsyncPipeline(
                    logging_provider=self.logging_provider
                )
            if not self._kg_search_pipeline:
                raise ValueError(
                    "KG search pipeline not found"
                )  # for type hinting

            self._kg_search_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        elif vector_search_pipe:
            if not self._vector_search_pipeline:
                self._vector_search_pipeline = AsyncPipeline(
                    logging_provider=self.logging_provider
                )
            if not self._vector_search_pipeline:
                raise ValueError(
                    "Vector search pipeline not found"
                )  # for type hinting

            self._vector_search_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        else:
            raise ValueError("Pipe must be a vector search or KG pipe")
