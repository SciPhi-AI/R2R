"""Abstractions for documents and their extractions."""

import base64
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import NAMESPACE_DNS, UUID, uuid4

from pydantic import BaseModel, Field, validator

from .base import R2RSerializable

logger = logging.getLogger(__name__)

DataType = Union[str, bytes]


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


class Document(R2RSerializable):
    id: UUID = Field(default_factory=uuid4)
    group_ids: list[UUID]
    user_id: UUID
    type: DocumentType
    data: Union[str, bytes]
    metadata: dict

    @validator("data")
    def validate_data(cls, v):
        if isinstance(v, (str, bytes)):
            return v
        raise ValueError("Data must be either str or bytes")

    def dict(self, *args, **kwargs):
        d = super().dict(*args, **kwargs)
        if isinstance(d["data"], bytes):
            d["data"] = base64.b64encode(d["data"]).decode("utf-8")
            d["_is_base64"] = True
        else:
            d["_is_base64"] = False
        return d

    @classmethod
    def parse_obj(cls, obj):
        if obj.get("_is_base64", False):
            obj["data"] = base64.b64decode(obj["data"])
        obj.pop("_is_base64", None)
        return super().parse_obj(obj)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            bytes: lambda v: base64.b64encode(v).decode("utf-8"),
        }


class IngestionStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"

    FAILURE = "failure"
    SUCCESS = "success"


class RestructureStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    FAILURE = "failure"
    SUCCESS = "success"


class DocumentInfo(R2RSerializable):
    """Base class for document information handling."""

    id: UUID
    group_ids: list[UUID]
    user_id: UUID
    type: DocumentType
    metadata: dict
    title: Optional[str] = None
    version: str
    size_in_bytes: int
    ingestion_status: IngestionStatus = IngestionStatus.PENDING
    restructuring_status: RestructureStatus = RestructureStatus.PROCESSING
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


class DocumentExtraction(R2RSerializable):
    """An extraction from a document."""

    id: UUID
    document_id: UUID
    group_ids: list[UUID]
    user_id: UUID
    data: DataType
    metadata: dict


class DocumentFragment(R2RSerializable):
    """A fragment extracted from a document."""

    id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    group_ids: list[UUID]
    data: DataType
    metadata: dict
