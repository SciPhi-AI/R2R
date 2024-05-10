"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipe`.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    AsyncState,
    LoggingDatabaseConnectionSingleton,
    PipeFlow,
    PipeType,
    VectorDBProvider,
    VectorEntry,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class DefaultVectorStoragePipe(LoggableAsyncPipe):
    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator[VectorEntry, None]
        do_upsert: bool = True

    """
    Stores embeddings in a vector database asynchronously.
    """

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        storage_batch_size: int = 128,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[LoggableAsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(
            f"Initalizing an `AsyncVectorStoragePipe` to store embeddings in a vector database."
        )

        super().__init__(
            logging_connection=logging_connection,
            flow=flow,
            type=type,
            config=config,
            *args,
            **kwargs,
        )
        self.vector_db_provider = vector_db_provider
        self.storage_batch_size = storage_batch_size

    async def store(
        self,
        vector_entries: list[VectorEntry],
        do_upsert: bool = True,
    ) -> None:
        """
        Stores a batch of vector entries in the database.
        """
        try:
            if do_upsert:
                self.vector_db_provider.upsert_entries(vector_entries)
            else:
                self.vector_db_provider.copy_entries(vector_entries)
        except Exception as e:
            logger.error(f"Error storing vector entries: {e}")
            raise

    async def _run_logic(
        self,
        input: AsyncGenerator[VectorEntry, None],
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[None, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        batch_tasks = []
        vector_batch = []

        async for vector_entry in input.message:
            vector_batch.append(vector_entry)
            if len(vector_batch) >= self.storage_batch_size:
                # Schedule the storage task
                batch_tasks.append(
                    asyncio.create_task(
                        self.store(vector_batch.copy(), input.do_upsert)
                    )
                )
                vector_batch.clear()

        if vector_batch:  # Process any remaining vectors
            batch_tasks.append(
                asyncio.create_task(
                    self.store(vector_batch.copy(), input.do_upsert)
                )
            )

        # Wait for all storage tasks to complete
        await asyncio.gather(*batch_tasks)
        yield None
