"""Abstractions for documents and their extractions."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import NAMESPACE_DNS, UUID, uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DataType = Union[str, bytes]


class DocumentStatus(str, Enum):
    """Status of document processing."""

    PROCESSING = "processing"
    # TODO - Extend support for `partial-failure`
    # PARTIAL_FAILURE = "partial-failure"
    FAILURE = "failure"
    SUCCESS = "success"


class DocumentType(str, Enum):
    """Types of documents that can be stored."""

    CSV = "csv"
    DOCX = "docx"
    HTML = "html"
    HTM = "htm"
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
    id: UUID = Field(default_factory=uuid4)
    group_ids: list[UUID]
    user_id: UUID

    type: DocumentType
    data: Union[str, bytes]
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
            data_hash = uuid4(NAMESPACE_DNS, data_str)
            kwargs["id"] = data_hash  # Set the id based on the data hash

        super().__init__(*args, **kwargs)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            bytes: lambda v: v.decode("utf-8", errors="ignore"),
        }


class DocumentInfo(BaseModel):
    """Base class for document information handling."""

    id: UUID
    group_ids: list[UUID]
    user_id: UUID
    type: DocumentType
    metadata: dict
    title: Optional[str] = None
    version: str
    size_in_bytes: int
    ingestion_status: DocumentStatus = DocumentStatus.PROCESSING
    restructuring_status: DocumentStatus = DocumentStatus.PROCESSING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain fields from metadata."""
        now = datetime.now()

        return {
            "document_id": self.id,
            "group_ids": self.group_ids,
            "user_id": self.user_id,
            "type": self.type,
            "metadata": json.dumps(self.metadata),
            "title": self.title or "N/A",
            "version": self.version,
            "size_in_bytes": self.size_in_bytes,
            "ingestion_status": self.ingestion_status,
            "restructuring_status": self.restructuring_status,
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
        }


class DocumentExtraction(BaseModel):
    """An extraction from a document."""

    id: UUID
    document_id: UUID
    group_ids: list[UUID]
    user_id: UUID
    data: DataType
    metadata: dict


class DocumentFragment(BaseModel):
    """A fragment extracted from a document."""

    id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    group_ids: list[UUID]
    data: DataType
    metadata: dict
