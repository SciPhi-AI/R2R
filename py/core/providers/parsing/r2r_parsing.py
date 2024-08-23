import logging
import time
from typing import Any, AsyncGenerator

from core import parsers
from core.base import (
    Document,
    DocumentExtraction,
    DocumentType,
    ParsingConfig,
    ParsingProvider,
    R2RDocumentProcessingError,
    generate_id_from_label,
)

logger = logging.getLogger(__name__)


class R2RParsingProvider(ParsingProvider):
    AVAILABLE_PARSERS = {
        DocumentType.CSV: [parsers.CSVParser, parsers.CSVParserAdvanced],
        DocumentType.DOCX: [parsers.DOCXParser],
        DocumentType.HTML: [parsers.HTMLParser],
        DocumentType.HTM: [parsers.HTMLParser],
        DocumentType.JSON: [parsers.JSONParser],
        DocumentType.MD: [parsers.MDParser],
        DocumentType.PDF: [parsers.PDFParser, parsers.PDFParserUnstructured],
        DocumentType.PPTX: [parsers.PPTParser],
        DocumentType.TXT: [parsers.TextParser],
        DocumentType.XLSX: [parsers.XLSXParser, parsers.XLSXParserAdvanced],
        DocumentType.GIF: [parsers.ImageParser],
        DocumentType.JPEG: [parsers.ImageParser],
        DocumentType.JPG: [parsers.ImageParser],
        DocumentType.PNG: [parsers.ImageParser],
        DocumentType.SVG: [parsers.ImageParser],
        DocumentType.MP3: [parsers.AudioParser],
        DocumentType.MP4: [parsers.MovieParser],
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(self, config: ParsingConfig):
        super().__init__(config)
        self.parsers = {}
        self._initialize_parsers()

    def _initialize_parsers(self):
        for doc_type, parser_infos in self.AVAILABLE_PARSERS.items():
            for parser_info in parser_infos:
                if (
                    doc_type not in self.config.excluded_parsers
                    and doc_type not in self.parsers
                ):
                    # will choose the first parser in the list
                    self.parsers[doc_type] = parser_info()

        # Apply overrides if specified
        for parser_override in self.config.override_parsers:
            parser_name = getattr(parsers, parser_override.parser)
            if parser_name:
                self.parsers[parser_override.document_type] = parser_name()

    async def parse(
        self, document: Document
    ) -> AsyncGenerator[DocumentExtraction, None]:
        if document.type not in self.parsers:
            yield R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Parser for {document.type} not found in `R2RParsingProvider`.",
            )
            return

        parser = self.parsers[document.type]
        texts = parser.ingest(document.data)
        t0 = time.time()

        iteration = 0
        async for text in texts:
            extraction = DocumentExtraction(
                id=generate_id_from_label(f"{document.id}-{iteration}"),
                document_id=document.id,
                user_id=document.user_id,
                group_ids=document.group_ids,
                data=text,
                metadata=document.metadata,
            )
            yield extraction
            iteration += 1

        logger.debug(
            f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
            f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
            f"into {iteration} extractions in t={time.time() - t0:.2f} seconds."
        )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> Any:
        return self.parsers.get(doc_type)
