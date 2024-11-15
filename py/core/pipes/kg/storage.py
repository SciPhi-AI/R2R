import asyncio
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncState,
    DatabaseProvider,
    KGExtraction,
    R2RDocumentProcessingError,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGStoragePipe(AsyncPipe):
    # TODO - Apply correct type hints to storage messages
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[list[Any], None]

    def __init__(
        self,
        database_provider: DatabaseProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        storage_batch_size: int = 1,
        *args,
        **kwargs,
    ):
        """
        Initializes the async knowledge graph storage pipe with necessary components and configurations.
        """
        logger.info(
            f"Initializing an `KGStoragePipe` to store knowledge graph extractions in a graph database."
        )

        super().__init__(
            config,
            logging_provider,
            *args,
            **kwargs,
        )
        self.database_provider = database_provider
        self.storage_batch_size = storage_batch_size

    async def store(
        self,
        kg_extractions: list[KGExtraction],
    ) -> None:
        """
        Stores a batch of knowledge graph extractions in the graph database.
        """
        try:
            # clean up and remove this method.
            # make add_kg_extractions a method in the GraphHandler

            total_entities, total_relationships = 0, 0

            for extraction in kg_extractions:

                total_entities, total_relationships = (
                    total_entities + len(extraction.entities),
                    total_relationships + len(extraction.relationships),
                )

                if extraction.entities:
                    if not extraction.entities[0].chunk_ids:
                        for i in range(len(extraction.entities)):
                            extraction.entities[i].chunk_ids = (
                                extraction.chunk_ids
                            )
                            extraction.entities[i].document_id = (
                                extraction.document_id
                            )

                    await self.database_provider.graph_handler.add_entities(
                        extraction.entities, table_name=f"chunk_entity"
                    )

                if extraction.relationships:
                    if not extraction.relationships[0].chunk_ids:
                        for i in range(len(extraction.relationships)):
                            extraction.relationships[i].chunk_ids = (
                                extraction.chunk_ids
                            )
                        extraction.relationships[i].document_id = (
                            extraction.document_id
                        )

                    await self.database_provider.graph_handler.add_relationships(
                        extraction.relationships,
                        table_name=f"chunk_relationship",
                    )

                return (total_entities, total_relationships)

        except Exception as e:
            error_message = f"Failed to store knowledge graph extractions in the database: {e}"
            logger.error(error_message)
            raise ValueError(error_message)

    async def _run_logic(  # type: ignore
        self,
        input: Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[list[R2RDocumentProcessingError], None]:
        """
        Executes the async knowledge graph storage pipe: storing knowledge graph extractions in the graph database.
        """

        batch_tasks = []
        kg_batch: list[KGExtraction] = []
        errors = []

        async for kg_extraction in input.message:
            if isinstance(kg_extraction, R2RDocumentProcessingError):
                errors.append(kg_extraction)
                continue

            kg_batch.append(kg_extraction)  # type: ignore
            if len(kg_batch) >= self.storage_batch_size:
                # Schedule the storage task
                batch_tasks.append(
                    asyncio.create_task(
                        self.store(kg_batch.copy()),
                        name=f"kg-store-{self.config.name}",
                    )
                )
                kg_batch.clear()

        if kg_batch:  # Process any remaining extractions
            batch_tasks.append(
                asyncio.create_task(
                    self.store(kg_batch.copy()),
                    name=f"kg-store-{self.config.name}",
                )
            )

        # Wait for all storage tasks to complete
        await asyncio.gather(*batch_tasks)

        for error in errors:
            yield error
