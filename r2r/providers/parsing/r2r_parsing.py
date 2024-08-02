import logging
import time
from typing import Any, AsyncGenerator

from r2r import parsers
from r2r.base import (
    Document,
    DocumentType,
    Extraction,
    ExtractionType,
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
    ) -> AsyncGenerator[Extraction, None]:
        if document.type not in self.parsers:
            yield R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Parser for {document.type} not found in `R2RParsingProvider`.",
            )
            return

        parser = self.parsers[document.type]
        texts = parser.ingest(document.data)
        extraction_type = ExtractionType.TXT
        t0 = time.time()

        if document.type in self.IMAGE_TYPES:
            extraction_type = ExtractionType.IMG
            document.metadata["image_type"] = document.type.value
        elif document.type == DocumentType.MP4:
            extraction_type = ExtractionType.MOV
            document.metadata["audio_type"] = document.type.value

        iteration = 0
        async for text in texts:
            extraction = Extraction(
                id=generate_id_from_label(f"{document.id}-{iteration}"),
                data=text,
                metadata=document.metadata,
                document_id=document.id,
                type=extraction_type,
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
