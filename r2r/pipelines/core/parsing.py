"""
A simple example to demonstrate the usage of `DefaultDocumentParsingPipeline`.
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional

from r2r.core import (
    Document,
    DocumentParsingPipeline,
    DocumentType,
    Extraction,
    LoggingDatabaseConnection,
)
from r2r.core.parsers import (
    CSVParser,
    DOCXParser,
    HTMLParser,
    JSONParser,
    MarkdownParser,
    Parser,
    PDFParser,
    PPTParser,
    TextParser,
    XLSXParser,
)
from r2r.core.utils import generate_id_from_label

logger = logging.getLogger(__name__)


class DefaultDocumentParsingPipeline(DocumentParsingPipeline):
    """
    Processes incoming documents into plaintext based on their data type.
    Supports TXT, JSON, HTML, and PDF formats.
    """

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
    }

    def __init__(
        self,
        selected_parsers: Optional[dict[DocumentType, Parser]] = None,
        override_parsers: Optional[dict[DocumentType, Parser]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ):
        logger.info(
            f"Initializing a `DefaultDocumentParsingPipeline` to process incoming documents."
        )

        super().__init__(
            logging_connection,
        )
        self.pipeline_run_info = None
        self.parsers = {}
        if selected_parsers is not None:
            for ingestion_type, parser in selected_parsers.items():
                if ingestion_type not in self.AVAILABLE_PARSERS:
                    raise ValueError(
                        f"parser for {ingestion_type} not supported by `DefaultDocumentParsingPipeline`."
                    )
                if parser not in self.AVAILABLE_PARSERS[ingestion_type]:
                    raise ValueError(
                        f"parser `{parser}` not available for `{ingestion_type}` in `DefaultDocumentParsingPipeline`."
                    )
                self.parsers[ingestion_type] = self.AVAILABLE_PARSERS[
                    ingestion_type
                ][parser]()
        else:
            self.parsers = {
                k: v["default"]()
                for k, v in DefaultDocumentParsingPipeline.AVAILABLE_PARSERS.items()
            }

        if override_parsers is not None:
            for entry_type, parser in override_parsers.items():
                self.parsers[entry_type] = parser

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipeline.
        """
        return [entry_type for entry_type in DocumentType]

    async def parse(
        self,
        document: Document,
    ) -> AsyncGenerator[Extraction, None]:
        if document.type not in self.parsers:
            logger.error(
                f"Parser for {document.type} not found in `AsyncBasicDocumentParsingPipeline`."
            )
            return
        parser = self.parsers[document.type]
        texts = parser.ingest(document.data)
        iteration = 0
        async for text in texts:
            extraction_id = generate_id_from_label(
                f"{document.id}-{iteration}"
            )
            yield Extraction(
                id=extraction_id,
                data=text,
                metadata=document.metadata,
                document_id=document.id,
            )
            iteration += 1

    async def run(
        self, documents: AsyncGenerator[Document, None]
    ) -> AsyncGenerator[Extraction, None]:
        self.initialize_pipeline()
        async for document in documents:
            async for extraction in self.parse(document):
                yield extraction
