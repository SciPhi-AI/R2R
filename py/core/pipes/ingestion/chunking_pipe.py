import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    ChunkingProvider,
    DocumentExtraction,
    DocumentFragment,
    PipeType,
    R2RChunkingConfig,
    RunLoggingSingleton,
    generate_id_from_label,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.providers import R2RChunkingProvider

logger = logging.getLogger(__name__)


class ChunkingPipe(AsyncPipe[DocumentFragment]):
    class Input(AsyncPipe.Input):
        message: list[DocumentExtraction]

    def __init__(
        self,
        chunking_provider: ChunkingProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            type,
            pipe_logger,
            *args,
            **kwargs,
        )
        self.default_chunking_provider = (
            chunking_provider or R2RChunkingProvider(R2RChunkingConfig())
        )

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[DocumentFragment, None]:

        chunking_provider = (
            kwargs.get("chunking_provider", None)
            or self.default_chunking_provider
        )

        unstr_iteration = 0  # unstructured already chunks
        for item in input.message:
            iteration = 0
            async for chunk in chunking_provider.chunk(item):  # type: ignore
                if item.metadata.get("partitioned_by_unstructured", False):
                    item.metadata["chunk_order"] = unstr_iteration
                    unstr_iteration += 1
                else:
                    item.metadata["chunk_order"] = iteration
                    iteration += 1

                yield DocumentFragment(
                    id=generate_id_from_label(f"{item.id}-{iteration}"),
                    extraction_id=item.id,
                    document_id=item.document_id,
                    user_id=item.user_id,
                    collection_ids=item.collection_ids,
                    data=chunk,
                    metadata=item.metadata,
                )
