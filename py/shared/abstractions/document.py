"""Abstractions for documents and their extractions."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid4

from pydantic import Field

from .base import R2RSerializable

logger = logging.getLogger(__name__)

DataType = Union[str, bytes]


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
    MP4 = "mp4"
    GIF = "gif"

    # Word
    DOC = "doc"
    DOCX = "docx"

    # XML
    XML = "xml"


class Document(R2RSerializable):
    id: UUID = Field(default_factory=uuid4)
    collection_ids: list[UUID]
    user_id: UUID
    type: DocumentType
    metadata: dict

    class Config:
        arbitrary_types_allowed = True
        ignore_extra = False
        json_encoders = {
            UUID: str,
        }


class IngestionStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"

    FAILED = "failed"
    SUCCESS = "success"


class KGExtractionStatus(str, Enum):
    """Status of KG Creation per document."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class KGEnrichmentStatus(str, Enum):
    """Status of KG Enrichment per collection."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class DocumentInfo(R2RSerializable):
    """Base class for document information handling."""

    id: UUID
    collection_ids: list[UUID]
    user_id: UUID
    type: DocumentType
    metadata: dict
    title: Optional[str] = None
    version: str
    size_in_bytes: int
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    kg_extraction_status: KGExtractionStatus = KGExtractionStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ingestion_attempt_number: Optional[int] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain fields from metadata."""
        now = datetime.now()

        return {
            "document_id": self.id,
            "collection_ids": self.collection_ids,
            "user_id": self.user_id,
            "type": self.type,
            "metadata": json.dumps(self.metadata),
            "title": self.title or "N/A",
            "version": self.version,
            "size_in_bytes": self.size_in_bytes,
            "ingestion_status": self.ingestion_status.value,
            "kg_extraction_status": self.kg_extraction_status.value,
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
            "ingestion_attempt_number": self.ingestion_attempt_number or 0,
        }


class DocumentExtraction(R2RSerializable):
    """An extraction from a document."""

    id: UUID
    document_id: UUID
    collection_ids: list[UUID]
    user_id: UUID
    data: DataType
    metadata: dict


class RawChunk(R2RSerializable):
    text: str
