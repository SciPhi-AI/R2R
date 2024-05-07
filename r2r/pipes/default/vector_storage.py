"""
A simple example to demonstrate the usage of `DefaultEmbeddingPipe`.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import LoggingDatabaseConnection, VectorDBProvider, VectorEntry

from ..abstractions.storage import StoragePipe

logger = logging.getLogger(__name__)


class DefaultVectorStoragePipe(StoragePipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        storage_batch_size: int = 128,
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
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
            **kwargs,
        )
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

    async def run(
        self,
        input: AsyncGenerator[VectorEntry, None],
        do_upsert: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        self._initialize_pipe()

        batch_tasks = []
        vector_batch = []

        async for vector_entry in input:
            vector_batch.append(vector_entry)
            if len(vector_batch) >= self.storage_batch_size:
                # Schedule the storage task
                batch_tasks.append(
                    asyncio.create_task(
                        self.store(vector_batch.copy(), do_upsert)
                    )
                )
                vector_batch.clear()

        if vector_batch:  # Process any remaining vectors
            batch_tasks.append(
                asyncio.create_task(self.store(vector_batch.copy(), do_upsert))
            )

        # Wait for all storage tasks to complete
        await asyncio.gather(*batch_tasks)
