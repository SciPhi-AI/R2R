# type: ignore
import logging
import time
from typing import Any, AsyncGenerator, Union

from core import parsers
from core.base import (
    AsyncParser,
    ChunkingMethod,
    Document,
    DocumentExtraction,
    DocumentType,
    IngestionConfig,
    IngestionProvider,
    R2RDocumentProcessingError,
    RecursiveCharacterTextSplitter,
    TextSplitter,
    generate_id_from_label,
)
from core.base.abstractions import DocumentExtraction

logger = logging.getLogger(__name__)


class R2RIngestionConfig(IngestionConfig):
    provider: str = "r2r"
    chunk_size: int = 1024
    chunk_overlap: int = 512
    chunking_method: ChunkingMethod = ChunkingMethod.RECURSIVE
    extra_fields: dict[str, Any] = {}


class R2RIngestionProvider(IngestionProvider):
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
    }

    IMAGE_TYPES = {
        DocumentType.GIF,
        DocumentType.JPG,
        DocumentType.JPEG,
        DocumentType.PNG,
        DocumentType.SVG,
    }

    def __init__(self, config: R2RIngestionConfig):
        super().__init__(config)
        self.config: R2RIngestionConfig = config  # for type hinting
        self.parsers: dict[DocumentType, AsyncParser] = {}
        self.text_splitter = self._initialize_text_splitter()
        self._initialize_parsers()

        logger.info(
            f"R2RIngestionProvider initialized with config: {self.config}"
        )

    def _initialize_parsers(self):
        for doc_type, parser_infos in self.AVAILABLE_PARSERS.items():
            for parser_info in parser_infos:
                if (
                    doc_type not in self.config.excluded_parsers
                    and doc_type not in self.parsers
                ):
                    # will choose the first parser in the list
                    self.parsers[doc_type] = parser_info()

    def _initialize_text_splitter(self) -> TextSplitter:
        logger.info(
            f"Initializing text splitter with method: {self.config.chunking_method}"
        )  # Debug log
        print("self.config.chunk_size=  ", self.config.chunk_size)
        if self.config.chunking_method == ChunkingMethod.RECURSIVE:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif self.config.chunking_method == ChunkingMethod.CHARACTER:
            from core.base.utils.splitter.text import CharacterTextSplitter

            separator = CharacterTextSplitter.DEFAULT_SEPARATOR
            if self.config.extra_fields:
                separator = self.config.extra_fields.get(
                    "separator", CharacterTextSplitter.DEFAULT_SEPARATOR
                )
            return CharacterTextSplitter(
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
                separator=separator,
                keep_separator=False,
                strip_whitespace=True,
            )
        elif self.config.chunking_method == ChunkingMethod.BASIC:
            raise NotImplementedError(
                "Basic chunking method not implemented. Please use Recursive."
            )
        elif self.config.chunking_method == ChunkingMethod.BY_TITLE:
            raise NotImplementedError("By title method not implemented")
        else:
            raise ValueError(
                f"Unsupported method type: {self.config.chunking_method}"
            )

    def validate_config(self) -> bool:
        return self.config.chunk_size > 0 and self.config.chunk_overlap >= 0

    def update_config(self, config_override: dict):
        if self.config != config_override:
            self.config = config_override
            self.text_splitter = self._initialize_text_splitter()

    def chunk(
        self, parsed_document: Union[str, DocumentExtraction]
    ) -> AsyncGenerator[Any, None]:
        if isinstance(parsed_document, DocumentExtraction):
            parsed_document = parsed_document.data

        if isinstance(parsed_document, str):
            chunks = self.text_splitter.create_documents([parsed_document])
        else:
            # Assuming parsed_document is already a list of text chunks
            chunks = parsed_document

        for chunk in chunks:
            yield (
                chunk.page_content if hasattr(chunk, "page_content") else chunk
            )

    async def parse(  # type: ignore
        self, file_content: bytes, document: Document
    ) -> AsyncGenerator[
        Union[DocumentExtraction, R2RDocumentProcessingError], None
    ]:
        if document.type not in self.parsers:
            yield R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Parser for {document.type} not found in `R2RIngestionProvider`.",
            )
        else:
            t0 = time.time()

            contents = ""
            async for text in self.parsers[document.type].ingest(file_content):
                contents += text + "\n"

            iteration = 0
            chunks = self.chunk(contents)
            for chunk in chunks:
                extraction = DocumentExtraction(
                    id=generate_id_from_label(f"{document.id}-{iteration}"),
                    document_id=document.id,
                    user_id=document.user_id,
                    collection_ids=document.collection_ids,
                    data=chunk,
                    metadata=document.metadata,
                )
                iteration += 1
                yield extraction

            logger.debug(
                f"Parsed document with id={document.id}, title={document.metadata.get('title', None)}, "
                f"user_id={document.metadata.get('user_id', None)}, metadata={document.metadata} "
                f"into {iteration} extractions in t={time.time() - t0:.2f} seconds."
            )

    def get_parser_for_document_type(self, doc_type: DocumentType) -> Any:
        return self.parsers.get(doc_type)
