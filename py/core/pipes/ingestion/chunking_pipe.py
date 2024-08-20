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
        message: AsyncGenerator[
            Union[DocumentExtraction, R2RDocumentProcessingError], None
        ]

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
        state: AsyncState,
        run_id: Any,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[
        Union[R2RDocumentProcessingError, DocumentFragment], None
    ]:

        chunking_provider = kwargs.get(
            "chunking_provider", self.default_chunking_provider
        )

        async for item in input.message:
            if isinstance(item, R2RDocumentProcessingError):
                yield item
                continue

            try:
                iteration = 0
                async for chunk in chunking_provider.chunk(item):
                    item.metadata["chunk_order"] = iteration
                    yield DocumentFragment(
                        id=generate_id_from_label(f"{item.id}-{iteration}"),
                        extraction_id=item.id,
                        document_id=item.document_id,
                        user_id=item.user_id,
                        group_ids=item.group_ids,
                        data=chunk,
                        metadata=item.metadata,
                    )
                    iteration += 1
            except Exception as e:
                logger.error(f"Error chunking document: {str(e)}")
                # print the traceback
                yield R2RDocumentProcessingError(
                    document_id=item.document_id,
                    error_message=f"Error chunking document: {str(e)}",
                )
