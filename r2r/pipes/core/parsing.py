"""
A simple example to demonstrate the usage of `DefaultDocumentParsingPipe`.
"""

import logging
from typing import AsyncGenerator, Optional

from r2r.core import (
    Document,
    DocumentParsingPipe,
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


class DefaultDocumentParsingPipe(DocumentParsingPipe):
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
        selected_parsers: Optional[dict[DocumentType, str]] = None,
        override_parsers: Optional[dict[DocumentType, Parser]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ):
        logger.info(
            "Initializing a `DefaultDocumentParsingPipe` to parse incoming documents."
        )
        super().__init__(logging_connection)

        # Initialize parsers with defaults and apply selected parsers
        self.parsers = {
            doc_type: self.AVAILABLE_PARSERS[doc_type]["default"]()
            for doc_type in DefaultDocumentParsingPipe.AVAILABLE_PARSERS
        }

        # Update with selected parsers if provided
        if selected_parsers:
            for doc_type, parser_key in selected_parsers.items():
                if doc_type not in self.parsers:
                    available_types = ", ".join(self.AVAILABLE_PARSERS.keys())
                    raise ValueError(
                        f"Unsupported document type '{doc_type}'. Supported types are: {available_types}"
                    )
                if parser_key not in self.AVAILABLE_PARSERS[doc_type]:
                    available_parsers = ", ".join(
                        self.AVAILABLE_PARSERS[doc_type].keys()
                    )
                    raise ValueError(
                        f"Parser '{parser_key}' not available for '{doc_type}'. Available parsers are: {available_parsers}"
                    )
                self.parsers[doc_type] = self.AVAILABLE_PARSERS[doc_type][
                    parser_key
                ]()

        # Apply overrides if provided
        if override_parsers:
            for doc_type, parser in override_parsers.items():
                if doc_type in self.parsers:
                    self.parsers[doc_type] = parser
                else:
                    logger.warning(
                        f"Attempting to override a parser for an unsupported document type '{doc_type}'."
                    )
        if override_parsers is not None:
            for entry_type, parser in override_parsers.items():
                self.parsers[entry_type] = parser

    async def parse(
        self,
        document: Document,
    ) -> AsyncGenerator[Extraction, None]:
        if document.type not in self.parsers:
            logger.error(
                f"Parser for {document.type} not found in `AsyncBasicDocumentParsingPipe`."
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
        self, input: AsyncGenerator[Document, None], *args, **kwargs
    ) -> AsyncGenerator[Extraction, None]:
        self._initialize_pipe()
        async for document in input:
            async for extraction in self.parse(document):
                yield extraction
