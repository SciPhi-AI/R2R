"""
This module contains the `DocumentParsingPipe` class, which is responsible for parsing incoming documents into plaintext.
"""

import logging
from typing import AsyncGenerator, Optional, Union
from uuid import UUID

from core.base import (
    AsyncState,
    Document,
    DocumentExtraction,
    ParsingProvider,
    PipeType,
    RunLoggingSingleton,
    generate_id_from_label,
)
from core.base.abstractions.exception import R2RDocumentProcessingError
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class ParsingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[Document, None]

    def __init__(
        self,
        parsing_provider: ParsingProvider,
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
            or AsyncPipe.PipeConfig(name="default_document_parsing_pipe"),
            *args,
            **kwargs,
        )
        self.parsing_provider = parsing_provider

    async def _parse(
        self,
        document: Document,
        run_id: UUID,
        version: str,
    ) -> AsyncGenerator[
        Union[R2RDocumentProcessingError, DocumentExtraction], None
    ]:
        try:
            async for extraction in self.parsing_provider.parse(document):
                extraction_id = generate_id_from_label(
                    f"{extraction.id}-{version}"
                )
                extraction.id = extraction_id
                # Add version to metadata
                extraction.metadata["version"] = version
                yield extraction
        except Exception as e:
            yield R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Error parsing document: {str(e)}",
            )

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: UUID,
        *args,
        **kwargs,
    ) -> AsyncGenerator[DocumentExtraction, None]:
        async for document in input.message:
            async for result in self._parse(
                document, run_id, document.metadata.get("version", "1.0")
            ):
                yield result
