"""Abstractions for documents and their extractions."""

import base64
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union

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
    metadata: dict

    def __init__(self, *args, **kwargs):
        data = kwargs.get("data")
        if data and isinstance(data, str):
            try:
                # Try to decode if it's already base64 encoded
                kwargs["data"] = base64.b64decode(data)
            except:
                # If it's not base64, encode it to bytes
                kwargs["data"] = data.encode("utf-8")

        # Generate UUID based on the hash of the data
        if "id" not in kwargs:
            if isinstance(kwargs["data"], bytes):
                data_hash = uuid.uuid5(
                    uuid.NAMESPACE_DNS, kwargs["data"].decode("utf-8")
                )
            else:
                data_hash = uuid.uuid5(uuid.NAMESPACE_DNS, kwargs["data"])

            kwargs["id"] = data_hash  # Set the id based on the data hash

        super().__init__(*args, **kwargs)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            uuid.UUID: str,
            bytes: lambda v: base64.b64encode(v).decode("utf-8"),
        }


class DocumentInfo(BaseModel):
    """Base class for document information handling."""

    document_id: uuid.UUID
    version: str
    size_in_bytes: int
    metadata: dict

    user_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain fields from metadata."""
        now = datetime.now()
        metadata = self.metadata
        metadata["user_id"] = (
            str(metadata["user_id"]) if "user_id" in metadata else None
        )
        metadata["title"] = metadata.get("title", "N/A")
        return {
            "document_id": str(self.document_id),
            "title": metadata.get("title", "N/A"),
            "user_id": metadata["user_id"],
            "version": self.version,
            "size_in_bytes": self.size_in_bytes,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at or now,
            "updated_at": self.updated_at or now,
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


class Fragment(BaseModel):
    """A fragment extracted from a document."""

    id: uuid.UUID
    type: FragmentType
    data: DataType
    metadata: dict
    document_id: uuid.UUID
    extraction_id: uuid.UUID


class Entity(BaseModel):
    """An entity extracted from a document."""

    category: str
    subcategory: Optional[str] = None
    value: str

    def __str__(self):
        return (
            f"{self.category}:{self.subcategory}:{self.value}"
            if self.subcategory
            else f"{self.category}:{self.value}"
        )


class Triple(BaseModel):
    """A triple extracted from a document."""

    subject: str
    predicate: str
    object: str


def extract_entities(llm_payload: list[str]) -> dict[str, Entity]:
    entities = {}
    for entry in llm_payload:
        try:
            if "], " in entry:  # Check if the entry is an entity
                entry_val = entry.split("], ")[0] + "]"
                entry = entry.split("], ")[1]
                colon_count = entry.count(":")

                if colon_count == 1:
                    category, value = entry.split(":")
                    subcategory = None
                elif colon_count >= 2:
                    parts = entry.split(":", 2)
                    category, subcategory, value = (
                        parts[0],
                        parts[1],
                        parts[2],
                    )
                else:
                    raise ValueError("Unexpected entry format")

                entities[entry_val] = Entity(
                    category=category, subcategory=subcategory, value=value
                )
        except Exception as e:
            logger.error(f"Error processing entity {entry}: {e}")
            continue
    return entities


def extract_triples(
    llm_payload: list[str], entities: dict[str, Entity]
) -> list[Triple]:
    triples = []
    for entry in llm_payload:
        try:
            if "], " not in entry:  # Check if the entry is an entity
                subject, predicate, object = entry.split(" ")
                subject = entities[subject].value  # Use entity.value
                if "[" in object and "]" in object:
                    object = entities[object].value  # Use entity.value
                triples.append(
                    Triple(subject=subject, predicate=predicate, object=object)
                )
        except Exception as e:
            logger.error(f"Error processing triplet {entry}: {e}")
            continue
    return triples


class KGExtraction(BaseModel):
    """An extraction from a document that is part of a knowledge graph."""

    entities: dict[str, Entity]
    triples: list[Triple]
