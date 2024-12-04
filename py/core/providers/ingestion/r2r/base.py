# type: ignore
import logging
import time
from typing import Any, AsyncGenerator, Optional, Union

from core import parsers
from core.base import (
    AsyncParser,
    ChunkingStrategy,
    Document,
    DocumentChunk,
    DocumentType,
    IngestionConfig,
    IngestionProvider,
    R2RDocumentProcessingError,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)
from core.base.abstractions import DocumentChunk
from core.utils import generate_extraction_id

from ...database import PostgresDBProvider
from ...llm import LiteLLMCompletionProvider, OpenAICompletionProvider

logger = logging.getLogger()


class R2RIngestionConfig(IngestionConfig):
    chunk_size: int = 1024
    chunk_overlap: int = 512
    chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    extra_fields: dict[str, Any] = {}
    separator: Optional[str] = None


class R2RIngestionProvider(IngestionProvider):
    DEFAULT_PARSERS = {
        DocumentType.CSV: parsers.CSVParser,
        DocumentType.DOCX: parsers.DOCXParser,
        DocumentType.HTML: parsers.HTMLParser,
        DocumentType.HTM: parsers.HTMLParser,
        DocumentType.JSON: parsers.JSONParser,
        DocumentType.MD: parsers.MDParser,
        DocumentType.PDF: parsers.BasicPDFParser,
        DocumentType.PPTX: parsers.PPTParser,
        DocumentType.TXT: parsers.TextParser,
        DocumentType.XLSX: parsers.XLSXParser,
        DocumentType.GIF: parsers.ImageParser,
        DocumentType.JPEG: parsers.ImageParser,
        DocumentType.JPG: parsers.ImageParser,
        DocumentType.PNG: parsers.ImageParser,
        DocumentType.SVG: parsers.ImageParser,
        DocumentType.MP3: parsers.AudioParser,
    }

    EXTRA_PARSERS = {
        DocumentType.CSV: {"advanced": parsers.CSVParserAdvanced},
        DocumentType.PDF: {
            "unstructured": parsers.PDFParserUnstructured,
            "zerox": parsers.VLMPDFParser,
        },
        DocumentType.XLSX: {"advanced": parsers.XLSXParserAdvanced},
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
        config: R2RIngestionConfig,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ],
    ):
        super().__init__(config, database_provider, llm_provider)
        self.config: R2RIngestionConfig = config  # for type hinting
        self.database_provider: PostgresDBProvider = database_provider
        self.llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ] = llm_provider
        self.parsers: dict[DocumentType, AsyncParser] = {}
        self.text_splitter = self._build_text_splitter()
        self._initialize_parsers()

        logger.info(
            f"R2RIngestionProvider initialized with config: {self.config}"
        )

    def _initialize_parsers(self):
        for doc_type, parser in self.DEFAULT_PARSERS.items():
            # will choose the first parser in the list
            if doc_type not in self.config.excluded_parsers:
                self.parsers[doc_type] = parser(
                    config=self.config,
                    database_provider=self.database_provider,
                    llm_provider=self.llm_provider,
                )
        for doc_type, doc_parser_name in self.config.extra_parsers.items():
            self.parsers[
                f"{doc_parser_name}_{str(doc_type)}"
            ] = R2RIngestionProvider.EXTRA_PARSERS[doc_type][doc_parser_name](
                config=self.config,
                database_provider=self.database_provider,
                llm_provider=self.llm_provider,
            )

    def _build_text_splitter(
        self, ingestion_config_override: Optional[dict] = None
    ) -> TextSplitter:
        logger.info(
            f"Initializing text splitter with method: {self.config.chunking_strategy}"
        )  # Debug log

        if not ingestion_config_override:
            ingestion_config_override = {}

        chunking_strategy = (
            ingestion_config_override.get("chunking_strategy", None)
            or self.config.chunking_strategy
        )

        chunk_size = (
            ingestion_config_override.get("chunk_size", None)
            or self.config.chunk_size
        )
        chunk_overlap = (
            ingestion_config_override.get("chunk_overlap", None)
            or self.config.chunk_overlap
        )

        if chunking_strategy == ChunkingStrategy.RECURSIVE:
            return RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        elif chunking_strategy == ChunkingStrategy.CHARACTER:
            from core.base.utils.splitter.text import CharacterTextSplitter

            separator = (
                ingestion_config_override.get("separator", None)
                or self.config.separator
                or CharacterTextSplitter.DEFAULT_SEPARATOR
            )

            return CharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separator=separator,
                keep_separator=False,
                strip_whitespace=True,
            )
        elif chunking_strategy == ChunkingStrategy.BASIC:
            raise NotImplementedError(
                "Basic chunking method not implemented. Please use Recursive."
            )
        elif chunking_strategy == ChunkingStrategy.BY_TITLE:
            raise NotImplementedError("By title method not implemented")
        else:
            raise ValueError(f"Unsupported method type: {chunking_strategy}")

    def validate_config(self) -> bool:
        return self.config.chunk_size > 0 and self.config.chunk_overlap >= 0

    def chunk(
        self,
        parsed_document: Union[str, DocumentChunk],
        ingestion_config_override: dict,
    ) -> AsyncGenerator[Any, None]:

        text_spliiter = self.text_splitter
        if ingestion_config_override:
            text_spliiter = self._build_text_splitter(
                ingestion_config_override
            )
        if isinstance(parsed_document, DocumentChunk):
            parsed_document = parsed_document.data

        if isinstance(parsed_document, str):
            chunks = text_spliiter.create_documents([parsed_document])
        else:
            # Assuming parsed_document is already a list of text chunks
            chunks = parsed_document

        for chunk in chunks:
            yield (
                chunk.page_content if hasattr(chunk, "page_content") else chunk
            )

    async def parse(  # type: ignore
        self,
        file_content: bytes,
        document: Document,
        ingestion_config_override: dict,
    ) -> AsyncGenerator[
        Union[DocumentChunk, R2RDocumentProcessingError], None
    ]:
        if document.document_type not in self.parsers:
            yield R2RDocumentProcessingError(
                document_id=document.id,
                error_message=f"Parser for {document.document_type} not found in `R2RIngestionProvider`.",
            )
        else:
            t0 = time.time()
            contents = ""
            parser_overrides = ingestion_config_override.get(
                "parser_overrides", {}
            )
            if document.document_type.value in parser_overrides:
                logger.info(
                    f"Using parser_override for {document.document_type} with input value {parser_overrides[document.document_type.value]}"
                )
                # TODO - Cleanup this approach to be less hardcoded
                if (
                    document.document_type != DocumentType.PDF
                    or parser_overrides[DocumentType.PDF.value] != "zerox"
                ):
                    raise ValueError(
                        "Only Zerox PDF parser override is available."
                    )
                async for text in self.parsers[
                    f"zerox_{DocumentType.PDF.value}"
                ].ingest(file_content, **ingestion_config_override):
                    contents += text + "\n"
            else:
                async for text in self.parsers[document.document_type].ingest(
                    file_content, **ingestion_config_override
                ):
                    contents += text + "\n"

            iteration = 0
            chunks = self.chunk(contents, ingestion_config_override)
            for chunk in chunks:
                extraction = DocumentChunk(
                    id=generate_extraction_id(document.id, iteration),
                    document_id=document.id,
                    owner_id=document.owner_id,
                    collection_ids=document.collection_ids,
                    data=chunk,
                    metadata={**document.metadata, "chunk_order": iteration},
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
