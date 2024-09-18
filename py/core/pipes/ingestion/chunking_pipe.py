import logging
from typing import Any, AsyncGenerator, Optional, Union

from core.base import (
    AsyncState,
    ChunkingConfig,
    ChunkingProvider,
    DocumentExtraction,
    DocumentFragment,
    PipeType,
    R2RDocumentProcessingError,
    RunLoggingSingleton,
    generate_id_from_label,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.providers import R2RChunkingProvider

logger = logging.getLogger(__name__)


class ChunkingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: list[DocumentExtraction]

    def __init__(
        self,
        chunking_provider: ChunkingProvider,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_chunking_pipe"),
            *args,
            **kwargs,
        )
        self.default_chunking_provider = (
            chunking_provider or R2RChunkingProvider(ChunkingConfig())
        )

    async def _run_logic(
        self,
        input: Input,
        state: Optional[AsyncState],
        run_id: Any,
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
            async for chunk in chunking_provider.chunk(item):

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
