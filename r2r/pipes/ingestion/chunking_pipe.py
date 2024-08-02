import asyncio
from typing import Any, AsyncGenerator, Optional, Union

from r2r.base import (
    AsyncState,
    ChunkingProvider,
    Extraction,
    Fragment,
    FragmentType,
    KVLoggingSingleton,
    PipeType,
    R2RDocumentProcessingError,
    generate_id_from_label,
)
from r2r.base.pipes.base_pipe import AsyncPipe


class ChunkingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[
            Union[Extraction, R2RDocumentProcessingError], None
        ]

    def __init__(
        self,
        chunking_provider: ChunkingProvider,
        pipe_logger: Optional[KVLoggingSingleton] = None,
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
        self.chunking_provider = chunking_provider

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: Any,
        chunking_config_override: Optional[ChunkingProvider] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Union[R2RDocumentProcessingError, Fragment], None]:
        async for item in input.message:
            if isinstance(item, R2RDocumentProcessingError):
                yield item
                continue

            try:
                iteration = 0
                async for chunk in self.chunking_provider.chunk(item.data):
                    yield Fragment(
                        id=generate_id_from_label(f"{item.id}-{iteration}"),
                        type=FragmentType.TEXT,
                        data=chunk,
                        metadata=item.metadata,
                        extraction_id=item.id,
                        document_id=item.document_id,
                    )
                    iteration += 1
            except Exception as e:
                yield R2RDocumentProcessingError(
                    document_id=item.document_id,
                    error_message=f"Error chunking document: {str(e)}",
                )
