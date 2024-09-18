import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Union

from core.base import (
    AsyncState,
    DocumentFragment,
    EmbeddingProvider,
    PipeType,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
    Vector,
    VectorEntry,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(AsyncPipe):
    """
    Embeds fragments using a specified embedding model.
    """

    class Input(AsyncPipe.Input):
        message: list[DocumentFragment]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        embedding_batch_size: int = 1,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_embedding_pipe"),
        )
        self.embedding_provider = embedding_provider
        self.embedding_batch_size = embedding_batch_size

    async def embed(self, fragments: list[DocumentFragment]) -> list[float]:
        return await self.embedding_provider.async_get_embeddings(
            [fragment.data for fragment in fragments],
            EmbeddingProvider.PipeStage.BASE,
        )

    async def _process_batch(
        self, fragment_batch: list[DocumentFragment]
    ) -> list[VectorEntry]:
        vectors = await self.embed(fragment_batch)
        return [
            VectorEntry(
                fragment_id=fragment.id,
                extraction_id=fragment.extraction_id,
                document_id=fragment.document_id,
                user_id=fragment.user_id,
                collection_ids=fragment.collection_ids,
                vector=Vector(data=raw_vector),
                text=fragment.data,
                metadata={
                    **fragment.metadata,
                },
            )
            for raw_vector, fragment in zip(vectors, fragment_batch)
        ]

    async def _run_logic(
        self,
        input: Input,
        state: Optional[AsyncState],
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorEntry, None]:
        fragment_batch = []
        batch_size = self.embedding_batch_size
        concurrent_limit = (
            self.embedding_provider.config.concurrent_request_limit
        )
        tasks = set()

        async def process_batch(batch):
            return await self._process_batch(batch)

        try:
            for item in input.message:
                fragment_batch.append(item)

                if len(fragment_batch) >= batch_size:
                    tasks.add(
                        asyncio.create_task(process_batch(fragment_batch))
                    )
                    fragment_batch = []

                while len(tasks) >= concurrent_limit:
                    done, tasks = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        for vector_entry in await task:
                            yield vector_entry

            if fragment_batch:
                tasks.add(asyncio.create_task(process_batch(fragment_batch)))

            for task in asyncio.as_completed(tasks):
                for vector_entry in await task:
                    yield vector_entry
        finally:
            # Ensure all tasks are completed
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            # Cancel the log worker task
            if self.log_worker_task and not self.log_worker_task.done():
                self.log_worker_task.cancel()
                try:
                    await self.log_worker_task
                except asyncio.CancelledError:
                    pass
            # Ensure the log queue is empty
            while not self.log_queue.empty():
                await self.log_queue.get()
                self.log_queue.task_done()

    async def _process_fragment(
        self, fragment: DocumentFragment
    ) -> Union[VectorEntry, R2RDocumentProcessingError]:
        try:
            vectors = await self.embedding_provider.async_get_embeddings(
                [fragment.data],
                EmbeddingProvider.PipeStage.BASE,
            )

            return VectorEntry(
                fragment_id=fragment.id,
                extraction_id=fragment.extraction_id,
                document_id=fragment.document_id,
                user_id=fragment.user_id,
                collection_ids=fragment.collection_ids,
                vector=Vector(data=vectors[0]),
                text=fragment.data,
                metadata={**fragment.metadata},
            )
        except Exception as e:
            logger.error(f"Error processing fragment: {e}")
            return R2RDocumentProcessingError(
                error_message=str(e),
                document_id=fragment.document_id,
            )
