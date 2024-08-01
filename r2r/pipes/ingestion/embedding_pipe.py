import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    EmbeddingProvider,
    Fragment,
    KVLoggingSingleton,
    PipeType,
    R2RDocumentProcessingError,
    Vector,
    VectorEntry,
)
from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(AsyncPipe):
    """
    Embeds fragments using a specified embedding model.
    """

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[Fragment, R2RDocumentProcessingError], None
        ]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        embedding_batch_size: int = 1,
        pipe_logger: Optional[KVLoggingSingleton] = None,
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

    async def embed(self, fragments: list[Fragment]) -> list[float]:
        return await self.embedding_provider.async_get_embeddings(
            [fragment.data for fragment in fragments],
            EmbeddingProvider.PipeStage.BASE,
        )

    async def _process_batch(
        self, fragment_batch: list[Fragment]
    ) -> list[VectorEntry]:
        vectors = await self.embed(fragment_batch)
        return [
            VectorEntry(
                id=fragment.id,
                vector=Vector(data=raw_vector),
                metadata={
                    "document_id": fragment.document_id,
                    "extraction_id": fragment.extraction_id,
                    "text": fragment.data,
                    **fragment.metadata,
                },
            )
            for raw_vector, fragment in zip(vectors, fragment_batch)
        ]

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[R2RDocumentProcessingError, VectorEntry], None]:
        fragment_batch = []

        async for item in input.message:
            if isinstance(item, R2RDocumentProcessingError):
                yield item
                continue

            fragment_batch.append(item)
            if len(fragment_batch) >= self.embedding_batch_size:
                try:
                    for vector_entry in await self._process_batch(
                        fragment_batch
                    ):
                        yield vector_entry
                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    yield R2RDocumentProcessingError(
                        error_message=str(e),
                        document_id=fragment_batch[0].document_id,
                    )
                finally:
                    fragment_batch.clear()

        if fragment_batch:
            try:
                for vector_entry in await self._process_batch(fragment_batch):
                    yield vector_entry
            except Exception as e:
                logger.error(f"Error processing final batch: {e}")
                yield R2RDocumentProcessingError(
                    error_message=str(e),
                    document_id=fragment_batch[0].document_id,
                )
