"""Abstractions for documents and their extractions."""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel

DataType = Union[str, bytes]


class DocumentType(Enum):
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
    """A document that has been stored in the system."""

    id: uuid.UUID
    type: DocumentType
    data: DataType
    metadata: dict

    title: Optional[str] = None
    user_id: Optional[uuid.UUID] = None


class DocumentInfo(BaseModel):
    """Base class for document information handling."""

    document_id: uuid.UUID
    version: str
    size_in_bytes: int
    metadata: dict

    title: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def convert_to_db_entry(self):
        """Prepare the document info for database entry, extracting certain fields from metadata."""
        now = datetime.now()
        return {
            "document_id": str(self.document_id),
            "title": self.title or "N/A",
            "user_id": str(self.user_id),
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
    sub_category: Optional[str] = None
    value: str


def extract_entities(entity_data: dict[str, str]) -> list[Entity]:
    entities = []
    for entity_key, entity_value in entity_data.items():
        parts = entity_value.split(":")
        if len(parts) == 2:
            category, value = parts
            sub_category = None
        else:
            category, sub_category, value = parts
        entities.append(
            Entity(category=category, sub_category=sub_category, value=value)
        )
    return entities


class Triple(BaseModel):
    """A triple extracted from a document."""

    subject: str
    predicate: str
    object: str


def extract_triples(
    triplet_data: list[str], entities: dict[str, str]
) -> list[Triple]:
    triples = []
    for triplet in triplet_data:
        parts = triplet.split(": ")
        subject_key = parts[0]
        predicate = parts[1]
        object_key = parts[2]

        subject = entities[subject_key]
        if object_key in entities:
            object = entities[object_key]
        else:
            object = object_key

        triples.append(
            Triple(subject=subject, predicate=predicate, object=object)
        )
    return triples


class KGExtraction(BaseModel):
    """An extraction from a document that is part of a knowledge graph."""

    entities: list[Entity]
    triples: list[Triple]
