import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Union

from core.base import (
    AsyncState,
    DocumentExtraction,
    EmbeddingProvider,
    PipeType,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
    Vector,
    VectorEntry,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(AsyncPipe[VectorEntry]):
    """
    Embeds extractions using a specified embedding model.
    """

    class Input(AsyncPipe.Input):
        message: list[DocumentExtraction]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        embedding_batch_size: int = 1,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            type,
            pipe_logger,
        )
        self.embedding_provider = embedding_provider
        self.embedding_batch_size = embedding_batch_size

    async def embed(
        self, extractions: list[DocumentExtraction]
    ) -> list[float]:
        return await self.embedding_provider.async_get_embeddings(
            [extraction.data for extraction in extractions],  # type: ignore
            EmbeddingProvider.PipeStage.BASE,
        )

    async def _process_batch(
        self, extraction_batch: list[DocumentExtraction]
    ) -> list[VectorEntry]:
        vectors = await self.embed(extraction_batch)
        return [
            VectorEntry(
                extraction_id=extraction.id,
                document_id=extraction.document_id,
                user_id=extraction.user_id,
                collection_ids=extraction.collection_ids,
                vector=Vector(data=raw_vector),
                text=extraction.data,  # type: ignore
                metadata={
                    **extraction.metadata,
                },
            )
            for raw_vector, extraction in zip(vectors, extraction_batch)
        ]

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorEntry, None]:
        if not isinstance(input, EmbeddingPipe.Input):
            raise ValueError(
                f"Invalid input type for embedding pipe: {type(input)}"
            )
        extraction_batch = []
        batch_size = self.embedding_batch_size
        concurrent_limit = (
            self.embedding_provider.config.concurrent_request_limit
        )
        tasks = set()

        async def process_batch(batch):
            return await self._process_batch(batch)

        try:
            for item in input.message:
                extraction_batch.append(item)

                if len(extraction_batch) >= batch_size:
                    tasks.add(
                        asyncio.create_task(process_batch(extraction_batch))
                    )
                    extraction_batch = []

                while len(tasks) >= concurrent_limit:
                    done, tasks = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        for vector_entry in await task:
                            yield vector_entry

            if extraction_batch:
                tasks.add(asyncio.create_task(process_batch(extraction_batch)))

            for future_task in asyncio.as_completed(tasks):
                for vector_entry in await future_task:
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

    async def _process_extraction(
        self, extraction: DocumentExtraction
    ) -> Union[VectorEntry, R2RDocumentProcessingError]:
        try:
            if isinstance(extraction.data, bytes):
                raise ValueError(
                    "extraction data is in bytes format, which is not supported by the embedding provider."
                )

            vectors = await self.embedding_provider.async_get_embeddings(
                [extraction.data],
                EmbeddingProvider.PipeStage.BASE,
            )

            return VectorEntry(
                extraction_id=extraction.id,
                document_id=extraction.document_id,
                user_id=extraction.user_id,
                collection_ids=extraction.collection_ids,
                vector=Vector(data=vectors[0]),
                text=extraction.data,
                metadata={**extraction.metadata},
            )
        except Exception as e:
            logger.error(f"Error processing extraction: {e}")
            return R2RDocumentProcessingError(
                error_message=str(e),
                document_id=extraction.document_id,
            )
