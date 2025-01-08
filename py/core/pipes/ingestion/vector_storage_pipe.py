import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import AsyncState, DatabaseProvider, StorageResult, VectorEntry
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger()


class VectorStoragePipe(AsyncPipe[StorageResult]):
    class Input(AsyncPipe.Input):
        message: list[VectorEntry]

    def __init__(
        self,
        database_provider: DatabaseProvider,
        config: AsyncPipe.PipeConfig,
        storage_batch_size: int = 128,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        super().__init__(
            config,
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
            await self.database_provider.chunks_handler.upsert_entries(
                vector_entries
            )
        except Exception as e:
            error_message = (
                f"Failed to store vector entries in the database: {e}"
            )
            logger.error(error_message)
            raise ValueError(error_message)

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[StorageResult, None]:
        vector_batch = []
        document_counts: dict[UUID, int] = {}
        current_usage = (
            await self.database_provider.chunks_handler.list_chunks(
                limit=1, offset=0, filters={"owner_id": msg.owner_id}
            )
        )["page_info"]["total_entries"]
        count = 0

        for msg in input.message:
            user = await self.database_provider.users_handler.get_user_by_id(
                msg.owner_id
            )
            max_chunks = (
                self.database_provider.config.app.default_max_chunks_per_user
            )
            if user.limits_overrides and "max_chunks" in user.limits_overrides:
                max_chunks = user.limits_overrides["max_chunks"]

            vector_batch.append(msg)
            document_counts[msg.document_id] = (
                document_counts.get(msg.document_id, 0) + 1
            )
            count += 1
            if current_usage + len(vector_batch) + count > max_chunks:
                error_message = f"User has exceeded the maximum number of allowed chunks: {max_chunks}"
                logger.error(error_message)
                yield StorageResult(
                    document_id=msg.document_id,
                    success=False,
                    error_message=error_message,
                )
                continue

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
            logger.info(
                f"Successful ingestion for document_id: {document_id}, with vector count: {count}"
            )
            yield StorageResult(
                document_id=document_id, num_chunks=count, success=True
            )
