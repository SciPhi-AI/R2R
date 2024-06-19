import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncState,
    KVLoggingSingleton,
    LoggableAsyncPipe,
    PipeType,
    VectorDBProvider,
    VectorEntry,
)

logger = logging.getLogger(__name__)


class VectorStoragePipe(LoggableAsyncPipe):
    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator[VectorEntry, None]
        do_upsert: bool = True

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        storage_batch_size: int = 128,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[LoggableAsyncPipe.PipeConfig] = None,
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
            error_message = (
                f"Failed to store vector entries in the database: {e}"
            )
            logger.error(error_message)
            raise ValueError(error_message)

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
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
                        self.store(vector_batch.copy(), input.do_upsert),
                        name=f"vector-store-{self.config.name}",
                    )
                )
                vector_batch.clear()

        if vector_batch:  # Process any remaining vectors
            batch_tasks.append(
                asyncio.create_task(
                    self.store(vector_batch.copy(), input.do_upsert),
                    name=f"vector-store-{self.config.name}",
                )
            )

        # Wait for all storage tasks to complete
        await asyncio.gather(*batch_tasks)
        yield None
