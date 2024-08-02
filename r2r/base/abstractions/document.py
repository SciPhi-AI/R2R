"""Abstractions for documents and their extractions."""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DataType = Union[str, bytes]


class DocumentType(str, Enum):
    """Types of documents that can be stored."""

    CSV = "csv"
    DOCX = "docx"
    HTML = "html"
    JSON = "json"
    MD = "md"
    PDF = "pdf"
    PPTX = "pptx"
    TXT = "txt"
    XLSX = "xlsx"
    GIF = "gif"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    SVG = "svg"
    MP3 = "mp3"
    MP4 = "mp4"


class Document(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: DocumentType
    data: Union[str, bytes]
    summary: Optional[str] | None = None
    summary_embedding: list[float] | None = None
    raw_content_embedding: list[float] | None = None
    metadata: dict

    def __init__(self, *args, **kwargs):
        doc_type = kwargs.get("type")
        if isinstance(doc_type, str):
            kwargs["type"] = DocumentType(doc_type)

        # Generate UUID based on the hash of the data
        if "id" not in kwargs:
            data = kwargs["data"]
            if isinstance(data, bytes):
                data_str = data.decode("utf-8", errors="ignore")
            else:
                data_str = data
            data_hash = uuid.uuid5(uuid.NAMESPACE_DNS, data_str)
            kwargs["id"] = data_hash  # Set the id based on the data hash

        super().__init__(*args, **kwargs)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            uuid.UUID: str,
            bytes: lambda v: v.decode("utf-8", errors="ignore"),
        }


class DocumentStatus(str, Enum):
    """Status of document processing."""

    PROCESSING = "processing"
    # TODO - Extend support for `partial-failure`
    # PARTIAL_FAILURE = "partial-failure"
    FAILURE = "failure"
    SUCCESS = "success"


class DocumentInfo(BaseModel):
    """Base class for document information handling."""

    document_id: uuid.UUID
    version: str
    size_in_bytes: int
    metadata: dict
    status: DocumentStatus = DocumentStatus.PROCESSING

    user_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain fields from metadata."""
        now = datetime.now()

        return {
            "document_id": str(self.document_id),
            "title": self.title or "N/A",
            "user_id": self.user_id,
            "version": self.version,
            "size_in_bytes": self.size_in_bytes,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
            "status": self.status,
        }


class ExtractionType(Enum):
    """Types of extractions that can be performed."""

    TXT = "txt"
    IMG = "img"
    MOV = "mov"


class Extraction(BaseModel):
    """An extraction from a document."""

    id: uuid.UUID
    type: ExtractionType = ExtractionType.TXT
    data: DataType
    metadata: dict
    document_id: uuid.UUID


class FragmentType(Enum):
    """A type of fragment that can be extracted from a document."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class Fragment(BaseModel):
    """A fragment extracted from a document."""

    id: uuid.UUID
    type: FragmentType
    data: DataType
    metadata: dict
    document_id: uuid.UUID
    extraction_id: uuid.UUID

