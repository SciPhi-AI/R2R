import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Tuple
from uuid import UUID

from core.base import (
    AsyncState,
    EmbeddingProvider,
    KGExtraction,
    PipeType,
    RunLoggingSingleton,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.base.providers import KGProvider

logger = logging.getLogger(__name__)


class KGStoragePipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[KGExtraction, None]

    def __init__(
        self,
        kg_provider: KGProvider,
        embedding_provider: Optional[EmbeddingProvider] = None,
        storage_batch_size: int = 1,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
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
            pipe_logger=pipe_logger,
            type=type,
            config=config,
            *args,
            **kwargs,
        )
        self.kg_provider = kg_provider
        self.embedding_provider = embedding_provider
        self.storage_batch_size = storage_batch_size

    async def store(
        self,
        kg_extractions: list[KGExtraction],
    ) -> Tuple[int, int]:
        """
        Stores a batch of knowledge graph extractions in the graph database.
        """
        try:
            return self.kg_provider.upsert_nodes_and_relationships(
                kg_extractions
            )
        except Exception as e:
            error_message = f"Failed to store knowledge graph extractions in the database: {e}"
            logger.error(error_message)
            raise ValueError(error_message)

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Tuple[int, int], None]:
        """
        Executes the async knowledge graph storage pipe: storing knowledge graph extractions in the graph database.
        """
        batch_tasks = []
        kg_batch = []

        async for kg_extraction in input.message:
            kg_batch.append(kg_extraction)
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
        results = await asyncio.gather(*batch_tasks)
        yield results
