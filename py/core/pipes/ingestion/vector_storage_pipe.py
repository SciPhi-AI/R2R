import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Tuple, Union
from uuid import UUID

from core.base import (
    AsyncState,
    DatabaseProvider,
    PipeType,
    RunLoggingSingleton,
    VectorEntry,
)
from core.base.abstractions.exception import R2RDocumentProcessingError
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class VectorStoragePipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[R2RDocumentProcessingError, VectorEntry], None
        ]

    def __init__(
        self,
        database_provider: DatabaseProvider,
        storage_batch_size: int = 128,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
            *args,
            **kwargs,
        )
        self.database_provider = database_provider
        self.storage_batch_size = storage_batch_size

    async def store(
        self,
        vector_entries: list[VectorEntry],
    ) -> None:
        """
        Stores a batch of vector entries in the database.
        """

        try:
            self.database_provider.vector.upsert_entries(vector_entries)
        except Exception as e:
            error_message = (
                f"Failed to store vector entries in the database: {e}"
            )
            logger.error(error_message)
            raise ValueError(error_message)

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[
        Tuple[UUID, Union[str, R2RDocumentProcessingError]], None
    ]:
        vector_batch = []
        document_counts = {}

        async for msg in input.message:
            if isinstance(msg, R2RDocumentProcessingError):
                yield (msg.document_id, msg)
                continue

            vector_batch.append(msg)
            document_counts[msg.document_id] = (
                document_counts.get(msg.document_id, 0) + 1
            )

            if len(vector_batch) >= self.storage_batch_size:
                try:
                    await self.store(vector_batch)
                except Exception as e:
                    logger.error(f"Failed to store vector batch: {e}")
                vector_batch.clear()

        if vector_batch:
            try:
                await self.store(vector_batch)
            except Exception as e:
                logger.error(f"Failed to store final vector batch: {e}")

        for document_id, count in document_counts.items():
            yield (
                document_id,
                f"Processed {count} vectors for document {document_id}.",
            )
