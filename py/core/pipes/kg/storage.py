import asyncio
import logging
from typing import Any, AsyncGenerator, List, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    EmbeddingProvider,
    KGExtraction,
    PipeType,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.base.providers import KGProvider

logger = logging.getLogger(__name__)


class KGStoragePipe(AsyncPipe):
    # TODO - Apply correct type hints to storage messages
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[List[Any], None]

    def __init__(
        self,
        kg_provider: KGProvider,
        config: AsyncPipe.PipeConfig,
        storage_batch_size: int = 1,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
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
            type,
            pipe_logger,
            *args,
            **kwargs,
        )
        self.kg_provider = kg_provider
        self.storage_batch_size = storage_batch_size

    async def store(
        self,
        kg_extractions: list[KGExtraction],
    ) -> None:
        """
        Stores a batch of knowledge graph extractions in the graph database.
        """
        try:
            await self.kg_provider.add_kg_extractions(kg_extractions)
            return
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
    ) -> AsyncGenerator[List[R2RDocumentProcessingError], None]:
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
