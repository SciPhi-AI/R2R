import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from r2r.base.logging.kv_logger import KVLoggingSingleton
from r2r.base.logging.run_manager import RunManager, manage_run
from r2r.base.pipeline.base_pipeline import AsyncPipeline, dequeue_requests
from r2r.base.pipes.base_pipe import AsyncPipe, AsyncState

logger = logging.getLogger(__name__)


class IngestionPipeline(AsyncPipeline):
    """A pipeline for ingestion."""

    pipeline_type: str = "ingestion"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        self.parsing_pipe = None
        self.embedding_pipeline = None
        self.kg_pipeline = None

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        stream: bool = False,
        run_manager: Optional[RunManager] = None,
        log_run_info: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.state = state or AsyncState()
        async with manage_run(run_manager, self.pipeline_type):
            if log_run_info:
                await run_manager.log_run_info(
                    key="pipeline_type",
                    value=self.pipeline_type,
                    is_info_log=True,
                )
            if self.parsing_pipe is None:
                raise ValueError(
                    "parsing_pipeline must be set before running the ingestion pipeline"
                )
            if self.embedding_pipeline is None and self.kg_pipeline is None:
                raise ValueError(
                    "At least one of embedding_pipeline or kg_pipeline must be set before running the ingestion pipeline"
                )
            # Use queues to duplicate the documents for each pipeline
            embedding_queue = Queue()
            kg_queue = Queue()

            async def enqueue_documents():
                async for document in await self.parsing_pipe.run(
                    self.parsing_pipe.Input(message=input),
                    state,
                    run_manager,
                    *args,
                    **kwargs,
                ):
                    if self.embedding_pipeline:
                        await embedding_queue.put(document)
                    if self.kg_pipeline:
                        await kg_queue.put(document)
                await embedding_queue.put(None)
                await kg_queue.put(None)

            # Start the document enqueuing process
            enqueue_task = asyncio.create_task(enqueue_documents())

            # Start the embedding and KG pipelines in parallel
            if self.embedding_pipeline:
                embedding_task = asyncio.create_task(
                    self.embedding_pipeline.run(
                        dequeue_requests(embedding_queue),
                        state,
                        stream,
                        run_manager,
                        log_run_info=False,  # Do not log run info since we have already done so
                        *args,
                        **kwargs,
                    )
                )

            if self.kg_pipeline:
                kg_task = asyncio.create_task(
                    self.kg_pipeline.run(
                        dequeue_requests(kg_queue),
                        state,
                        stream,
                        run_manager,
                        log_run_info=False,  # Do not log run info since we have already done so
                        *args,
                        **kwargs,
                    )
                )

            # Wait for the enqueueing task to complete
            await enqueue_task

            results = {}
            # Wait for the embedding and KG tasks to complete
            if self.embedding_pipeline:
                results["embedding_pipeline_output"] = await embedding_task
            if self.kg_pipeline:
                results["kg_pipeline_output"] = await kg_task
            return results

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        parsing_pipe: bool = False,
        kg_pipe: bool = False,
        embedding_pipe: bool = False,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(
            f"Adding pipe {pipe.config.name} to the IngestionPipeline"
        )

        if parsing_pipe:
            self.parsing_pipe = pipe
        elif kg_pipe:
            if not self.kg_pipeline:
                self.kg_pipeline = AsyncPipeline()
            self.kg_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        elif embedding_pipe:
            if not self.embedding_pipeline:
                self.embedding_pipeline = AsyncPipeline()
            self.embedding_pipeline.add_pipe(
                pipe, add_upstream_outputs, *args, **kwargs
            )
        else:
            raise ValueError("Pipe must be a parsing, embedding, or KG pipe")
