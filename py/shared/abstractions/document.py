"""Abstractions for documents and their extractions."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig

logger = logging.getLogger()


class DocumentType(str, Enum):
    """Types of documents that can be stored."""

    # Audio
    MP3 = "mp3"

    # CSV
    CSV = "csv"

    # Email
    EML = "eml"
    MSG = "msg"
    P7S = "p7s"

    # EPUB
    EPUB = "epub"

    # Excel
    XLS = "xls"
    XLSX = "xlsx"

    # HTML
    HTML = "html"
    HTM = "htm"

    # Image
    BMP = "bmp"
    HEIC = "heic"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    JPG = "jpg"
    SVG = "svg"

    # Markdown
    MD = "md"

    # Org Mode
    ORG = "org"

    # Open Office
    ODT = "odt"

    # PDF
    PDF = "pdf"

    # Plain text
    TXT = "txt"
    JSON = "json"

    # PowerPoint
    PPT = "ppt"
    PPTX = "pptx"

    # reStructured Text
    RST = "rst"

    # Rich Text
    RTF = "rtf"

    # TSV
    TSV = "tsv"

    # Video/GIF
    GIF = "gif"

    # Word
    DOC = "doc"
    DOCX = "docx"

    # XML
    XML = "xml"


class Document(R2RSerializable):
    id: UUID = Field(default_factory=uuid4)
    collection_ids: list[UUID]
    owner_id: UUID
    document_type: DocumentType
    metadata: dict

    class Config:
        arbitrary_types_allowed = True
        ignore_extra = False
        json_encoders = {
            UUID: str,
        }
        populate_by_name = True


class IngestionStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    AUGMENTING = "augmenting"
    STORING = "storing"
    ENRICHING = "enriching"

    FAILED = "failed"
    SUCCESS = "success"

    def __str__(self):
        return self.value

    @classmethod
    def table_name(cls) -> str:
        return "documents"

    @classmethod
    def id_column(cls) -> str:
        return "document_id"


class GraphExtractionStatus(str, Enum):
    """Status of graph creation per document."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ENRICHED = "enriched"
    FAILED = "failed"

    def __str__(self):
        return self.value

    @classmethod
    def table_name(cls) -> str:
        return "documents"

    @classmethod
    def id_column(cls) -> str:
        return "id"


class GraphConstructionStatus(str, Enum):
    """Status of graph enrichment per collection."""

    PENDING = "pending"
    PROCESSING = "processing"
    OUTDATED = "outdated"
    SUCCESS = "success"
    FAILED = "failed"

    def __str__(self):
        return self.value

    @classmethod
    def table_name(cls) -> str:
        return "collections"

    @classmethod
    def id_column(cls) -> str:
        return "id"


class DocumentResponse(R2RSerializable):
    """Base class for document information handling."""

    id: UUID
    collection_ids: list[UUID]
    owner_id: UUID
    document_type: DocumentType
    metadata: dict
    title: Optional[str] = None
    version: str
    size_in_bytes: Optional[int]
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    extraction_status: GraphExtractionStatus = GraphExtractionStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ingestion_attempt_number: Optional[int] = None
    summary: Optional[str] = None
    summary_embedding: Optional[list[float]] = None  # Add optional embedding
    total_tokens: Optional[int] = None
    chunks: Optional[list] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain
        fields from metadata."""
        now = datetime.now()

        # Format the embedding properly for Postgres vector type
        embedding = None
        if self.summary_embedding is not None:
            embedding = f"[{','.join(str(x) for x in self.summary_embedding)}]"

        return {
            "id": self.id,
            "collection_ids": self.collection_ids,
            "owner_id": self.owner_id,
            "document_type": self.document_type,
            "metadata": json.dumps(self.metadata),
            "title": self.title or "N/A",
            "version": self.version,
            "size_in_bytes": self.size_in_bytes,
            "ingestion_status": self.ingestion_status.value,
            "extraction_status": self.extraction_status.value,
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
            "ingestion_attempt_number": self.ingestion_attempt_number or 0,
            "summary": self.summary,
            "summary_embedding": embedding,
            "total_tokens": self.total_tokens or 0,  # ensure we pass 0 if None
        }

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "collection_ids": ["123e4567-e89b-12d3-a456-426614174000"],
                "owner_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_type": "pdf",
                "metadata": {"title": "Sample Document"},
                "title": "Sample Document",
                "version": "1.0",
                "size_in_bytes": 123456,
                "ingestion_status": "pending",
                "extraction_status": "pending",
                "created_at": "2021-01-01T00:00:00",
                "updated_at": "2021-01-01T00:00:00",
                "ingestion_attempt_number": 0,
                "summary": "A summary of the document",
                "summary_embedding": [0.1, 0.2, 0.3],
                "total_tokens": 1000,
            }
        }


class UnprocessedChunk(R2RSerializable):
    """An extraction from a document."""

    id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    collection_ids: list[UUID] = []
    metadata: dict = {}
    text: str


class UpdateChunk(R2RSerializable):
    """An extraction from a document."""

    id: UUID
    metadata: Optional[dict] = None
    text: str


class DocumentChunk(R2RSerializable):
    """An extraction from a document."""

    id: UUID
    document_id: UUID
    collection_ids: list[UUID]
    owner_id: UUID
    data: str | bytes
    metadata: dict


class RawChunk(R2RSerializable):
    text: str


class IngestionMode(str, Enum):
    hi_res = "hi-res"
    fast = "fast"
    custom = "custom"


class ChunkEnrichmentSettings(R2RSerializable):
    """Settings for chunk enrichment."""

    enable_chunk_enrichment: bool = Field(
        default=False,
        description="Whether to enable chunk enrichment or not",
    )
    n_chunks: int = Field(
        default=2,
        description="The number of preceding and succeeding chunks to include. Defaults to 2.",
    )
    generation_config: Optional[GenerationConfig] = Field(
        default=None,
        description="The generation config to use for chunk enrichment",
    )
    chunk_enrichment_prompt: Optional[str] = Field(
        default="chunk_enrichment",
        description="The prompt to use for chunk enrichment",
    )


class IngestionConfig(R2RSerializable):
    provider: str = "r2r"
    excluded_parsers: list[str] = ["mp4"]
    chunking_strategy: str = "recursive"
    chunk_enrichment_settings: ChunkEnrichmentSettings = (
        ChunkEnrichmentSettings()
    )
    extra_parsers: dict[str, Any] = {}

    audio_transcription_model: str = ""

    vision_img_prompt_name: str = "vision_img"
    vision_img_model: str = ""

    vision_pdf_prompt_name: str = "vision_pdf"
    vision_pdf_model: str = ""

    skip_document_summary: bool = False
    document_summary_system_prompt: str = "system"
    document_summary_task_prompt: str = "summary"
    chunks_for_document_summary: int = 128
    document_summary_model: str = ""

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api"]

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")

    @classmethod
    def get_default(cls, mode: str) -> "IngestionConfig":
        """Return default ingestion configuration for a given mode."""
        if mode == "hi-res":
            # More thorough parsing, no skipping summaries, possibly larger `chunks_for_document_summary`.
            return cls(
                provider="r2r",
                excluded_parsers=["mp4"],
                chunk_enrichment_settings=ChunkEnrichmentSettings(),  # default
                extra_parsers={},
                audio_transcription_model="",
                vision_img_prompt_name="vision_img",
                vision_img_model="",
                vision_pdf_prompt_name="vision_pdf",
                vision_pdf_model="",
                skip_document_summary=False,
                document_summary_system_prompt="system",
                document_summary_task_prompt="summary",
                chunks_for_document_summary=256,  # larger for hi-res
                document_summary_model="",
            )

        elif mode == "fast":
            # Skip summaries and other enrichment steps for speed.
            return cls(
                provider="r2r",
                excluded_parsers=["mp4"],
                chunk_enrichment_settings=ChunkEnrichmentSettings(),  # default
                extra_parsers={},
                audio_transcription_model="",
                vision_img_prompt_name="vision_img",
                vision_img_model="",
                vision_pdf_prompt_name="vision_pdf",
                vision_pdf_model="",
                skip_document_summary=True,  # skip summaries
                document_summary_system_prompt="system",
                document_summary_task_prompt="summary",
                chunks_for_document_summary=64,
                document_summary_model="",
            )
        else:
            # For `custom` or any unrecognized mode, return a base config
            return cls()
