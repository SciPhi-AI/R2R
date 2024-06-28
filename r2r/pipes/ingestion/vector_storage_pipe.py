import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Optional, Tuple, Union

from r2r.base import (
    AsyncState,
    KVLoggingSingleton,
    PipeType,
    VectorDBProvider,
    VectorEntry,
)
from r2r.base.pipes.base_pipe import AsyncPipe

from .parsing_pipe import DocumentProcessingError

logger = logging.getLogger(__name__)


class VectorStoragePipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[DocumentProcessingError, VectorEntry], None
        ]
        do_upsert: bool = True

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        storage_batch_size: int = 128,
        pipe_logger: Optional[KVLoggingSingleton] = None,
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
    ) -> AsyncGenerator[
        Tuple[uuid.UUID, Union[str, DocumentProcessingError]], None
    ]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        batch_tasks = []
        vector_batch = []
        document_counts = {}
        async for msg in input.message:
            if isinstance(msg, DocumentProcessingError):
                yield (msg.document_id, msg)
                continue

            document_id = msg.metadata.get("document_id", None)
            if not document_id:
                raise ValueError("Document ID not found in the metadata.")
            if document_id not in document_counts:
                document_counts[document_id] = 1
            else:
                document_counts[document_id] += 1

            vector_batch.append(msg)
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

        for document_id, count in document_counts.items():
            yield (
                document_id,
                f"Processed {count} vectors for document {document_id}.",
            )
