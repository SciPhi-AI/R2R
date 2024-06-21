"""
This module contains the `DocumentParsingPipe` class, which is responsible for parsing incoming documents into plaintext.
"""

import asyncio
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from r2r.core import (
    AsyncParser,
    AsyncState,
    AudioParser,
    CSVParser,
    Document,
    DocumentType,
    DOCXParser,
    Extraction,
    ExtractionType,
    HTMLParser,
    ImageParser,
    JSONParser,
    KVLoggingSingleton,
    LoggableAsyncPipe,
    MarkdownParser,
    MovieParser,
    PDFParser,
    PipeType,
    PPTParser,
    TextParser,
    XLSXParser,
    generate_id_from_label,
)

logger = logging.getLogger(__name__)


class ParsingPipe(LoggableAsyncPipe):
    """
    Processes incoming documents into plaintext based on their data type.
    Supports TXT, JSON, HTML, and PDF formats.
    """

    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator[Document, None]

    AVAILABLE_PARSERS = {
        DocumentType.CSV: {"default": CSVParser},
        DocumentType.DOCX: {"default": DOCXParser},
        DocumentType.HTML: {"default": HTMLParser},
        DocumentType.JSON: {"default": JSONParser},
        DocumentType.MD: {"default": MarkdownParser},
        DocumentType.PDF: {"default": PDFParser},
        DocumentType.PPTX: {"default": PPTParser},
        DocumentType.TXT: {"default": TextParser},
        DocumentType.XLSX: {"default": XLSXParser},
        DocumentType.GIF: {"default": ImageParser},
        DocumentType.JPEG: {"default": ImageParser},
        DocumentType.JPG: {"default": ImageParser},
        DocumentType.PNG: {"default": ImageParser},
        DocumentType.SVG: {"default": ImageParser},
        DocumentType.MP3: {"default": AudioParser},
        DocumentType.MP4: {"default": MovieParser},
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(
        self,
        excluded_parsers: dict[DocumentType, AsyncParser],
        override_parsers: Optional[dict[DocumentType, AsyncParser]] = None,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[LoggableAsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config
            or LoggableAsyncPipe.PipeConfig(
                name="default_document_parsing_pipe"
            ),
            *args,
            **kwargs,
        )

        self.parsers = {}

        if not override_parsers:
            override_parsers = {}

        for doc_type, parser_info in self.AVAILABLE_PARSERS.items():
            if (
                doc_type not in excluded_parsers
                and doc_type not in self.parsers
            ):
                self.parsers[doc_type] = parser_info["default"]()

        # Apply overrides if specified
        for doc_type, parser in override_parsers.items():
            self.parsers[doc_type] = parser

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipe.
        """
        return [entry_type for entry_type in DocumentType]

    async def _parse(
        self,
        document: Document,
        run_id: uuid.UUID,
        version: str,
    ) -> AsyncGenerator[Extraction, None]:
        if document.type not in self.parsers:
            logger.error(
                f"Parser for {document.type} not found in `ParsingPipe`."
            )
            return
        parser = self.parsers[document.type]
        texts = parser.ingest(document.data)
        extraction_type = ExtractionType.TXT
        t0 = time.time()
        if document.type in self.IMAGE_TYPES:
            extraction_type = ExtractionType.IMG
            document.metadata["image_type"] = document.type.value
            # SAVE IMAGE DATA
            # try:
            #     import base64
            #     sanitized_data = base64.b64encode(document.data).decode('utf-8')
            # except Exception as e:
            #     sanitized_data = document.data

            # document.metadata["image_data"] = sanitized_data
        elif document.type == DocumentType.MP4:
            extraction_type = ExtractionType.MOV
            document.metadata["audio_type"] = document.type.value

        iteration = 0
        async for text in texts:
            extraction_id = generate_id_from_label(
                f"{document.id}-{iteration}-{version}"
            )
            document.metadata["version"] = version
            extraction = Extraction(
                id=extraction_id,
                data=text,
                metadata=document.metadata,
                document_id=document.id,
                type=extraction_type,
            )
            yield extraction
            # TODO - Add settings to enable extraction logging
            # extraction_dict = extraction.dict()
            # await self.enqueue_log(
            #     run_id=run_id,
            #     key="extraction",
            #     value=json.dumps(
            #         {
            #             "data": extraction_dict["data"],
            #             "document_id": str(extraction_dict["document_id"]),
            #             "extraction_id": str(extraction_dict["id"]),
            #         }
            #     ),
            # )
            iteration += 1
        logger.debug(
            f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} into {iteration} extractions in t={time.time()-t0:.2f} seconds."
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
        parse_tasks = []

        iteration = 0
        async for document in input.message:
            version = versions[iteration] if versions else "v0"
            iteration += 1
            parse_tasks.append(
                self._handle_parse_task(document, version, run_id)
            )

        # Await all tasks and yield results concurrently
        for parse_task in asyncio.as_completed(parse_tasks):
            for extraction in await parse_task:
                yield extraction

    async def _handle_parse_task(
        self, document: Document, version: str, run_id: uuid.UUID
    ) -> AsyncGenerator[Extraction, None]:
        extractions = []
        async for extraction in self._parse(document, run_id, version):
            extractions.append(extraction)
        return extractions
