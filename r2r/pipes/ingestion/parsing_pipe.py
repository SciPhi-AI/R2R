"""
This module contains the `DocumentParsingPipe` class, which is responsible for parsing incoming documents into plaintext.
"""

import asyncio
import logging
import time
import uuid
from typing import AsyncGenerator, Optional, Union

from r2r import parsers
from r2r.base import (
    AsyncState,
    Document,
    DocumentType,
    Extraction,
    ExtractionType,
    KVLoggingSingleton,
    ParsingProvider,
    PipeType,
    generate_id_from_label,
)
from r2r.base.abstractions.exception import R2RDocumentProcessingError
from r2r.base.pipes.base_pipe import AsyncPipe


class ParsingPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[Document, None]

    def __init__(
        self,
        parsing_provider: ParsingProvider,
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
            or AsyncPipe.PipeConfig(name="default_document_parsing_pipe"),
            *args,
            **kwargs,
        )
        self.parsing_provider = parsing_provider

    async def _parse(
        self,
        document: Document,
        run_id: uuid.UUID,
        version: str,
    ) -> AsyncGenerator[Union[R2RDocumentProcessingError, Extraction], None]:
        try:
            async for extraction in self.parsing_provider.parse(document):
                extraction_id = generate_id_from_label(
                    f"{extraction.id}-{version}"
                )
                extraction.id = extraction_id
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
        run_id: uuid.UUID,
        versions: Optional[list[str]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[Extraction, None]:
        async for document in input.message:
            version = versions[0] if versions else "v0"
            async for result in self._parse(document, run_id, version):
                yield result
