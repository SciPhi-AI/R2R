import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from core.base.api.models.auth.responses import UserResponse
from core.base.logging.run_logger import RunLoggingSingleton
from core.base.logging.run_manager import RunManager, manage_run
from core.base.pipeline.base_pipeline import AsyncPipeline, dequeue_requests
from core.base.pipes.base_pipe import AsyncPipe, AsyncState
from core.base.providers.chunking import ChunkingProvider

logger = logging.getLogger(__name__)


class IngestionPipeline(AsyncPipeline):
    """A pipeline for ingestion."""

    def __init__(
        self,
        pipe_logger: Optional[RunLoggingSingleton] = None,
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
        chunking_settings: Optional[ChunkingProvider] = None,
        user: Optional[UserResponse] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.state = state or AsyncState()
        if self.parsing_pipe is None:
            raise ValueError(
                "parsing_pipe must be set before running the ingestion pipeline"
            )
        if self.chunking_pipe is None:
            raise ValueError(
                "chunking_pipe must be set before running the ingestion pipeline"
            )
        if self.embedding_pipeline is None and self.kg_pipeline is None:
            raise ValueError(
                "At least one of embedding_pipeline or kg_pipeline must be set before running the ingestion pipeline"
            )

        # Use queues to pass data between pipes and duplicate for each pipeline
        parsing_to_chunking_queue = Queue()
        embedding_queue = Queue()
        kg_queue = Queue()

        async def process_documents():
            async for parsed_doc in await self.parsing_pipe.run(
                self.parsing_pipe.Input(message=input),
                state,
                run_manager,
                *args,
                **kwargs,
            ):
                await parsing_to_chunking_queue.put(parsed_doc)
            await parsing_to_chunking_queue.put(None)

            async for chunked_doc in await self.chunking_pipe.run(
                self.chunking_pipe.Input(
                    message=dequeue_requests(parsing_to_chunking_queue)
                ),
                state,
                run_manager,
                chunking_settings=chunking_settings,
                *args,
                **kwargs,
            ):
                if self.embedding_pipeline:
                    await embedding_queue.put(chunked_doc)
                if self.kg_pipeline:
                    await kg_queue.put(chunked_doc)
            await embedding_queue.put(None)
            await kg_queue.put(None)

        # Start the document processing
        process_task = asyncio.create_task(process_documents())

        # Start the embedding and KG pipelines in parallel
        tasks = []
        if self.embedding_pipeline:
            embedding_task = asyncio.create_task(
                self.embedding_pipeline.run(
                    dequeue_requests(embedding_queue),
                    state,
                    stream,
                    run_manager,
                    *args,
                    **kwargs,
                )
            )
            tasks.append(embedding_task)

        if self.kg_pipeline:
            kg_task = asyncio.create_task(
                self.kg_pipeline.run(
                    dequeue_requests(kg_queue),
                    state,
                    stream,
                    run_manager,
                    *args,
                    **kwargs,
                )
            )
            tasks.append(kg_task)

        # Wait for all tasks to complete
        await process_task
        results = await asyncio.gather(*tasks)

        return {
            "embedding_pipeline_output": (
                results[0] if self.embedding_pipeline else None
            ),
            "kg_pipeline_output": (results[-1] if self.kg_pipeline else None),
        }

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        parsing_pipe: bool = False,
        kg_pipe: bool = False,
        chunking_pipe: bool = False,
        embedding_pipe: bool = False,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(
            f"Adding pipe {pipe.config.name} to the IngestionPipeline"
        )

        if parsing_pipe:
            self.parsing_pipe = pipe
        elif chunking_pipe:
            self.chunking_pipe = pipe
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
