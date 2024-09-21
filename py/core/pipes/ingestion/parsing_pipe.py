import logging
from typing import AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    Document,
    DocumentExtraction,
    FileProvider,
    ParsingProvider,
    PipeType,
    RunLoggingSingleton,
    generate_id_from_label,
)
from core.base.abstractions import R2RDocumentProcessingError
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class ParsingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: Document

    def __init__(
        self,
        parsing_provider: ParsingProvider,
        file_provider: FileProvider,
        config: AsyncPipe.PipeConfig,
        type: PipeType = PipeType.INGESTOR,
        pipe_logger: Optional[RunLoggingSingleton] = None,
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
        self.parsing_provider = parsing_provider
        self.file_provider = file_provider

    async def _parse(
        self,
        document: Document,
        run_id: UUID,
        version: str,
    ) -> AsyncGenerator[DocumentExtraction, None]:
        try:
            if result := await self.file_provider.retrieve_file(document.id):
                file_name, file_wrapper, file_size = result

            with file_wrapper as file_content_stream:
                file_content = file_content_stream.read()

            async for extraction in self.parsing_provider.parse(  # type: ignore
                file_content, document
            ):
                extraction_id = generate_id_from_label(
                    f"{extraction.id}-{version}"
                )
                extraction.id = extraction_id
                extraction.metadata["version"] = version
                yield extraction
        except Exception as e:
            raise R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Error parsing document: {str(e)}",
            )

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args,
        **kwargs,
    ) -> AsyncGenerator[DocumentExtraction, None]:
        async for result in self._parse(
            input.message, run_id, input.message.metadata.get("version", "v0")
        ):
            yield result
