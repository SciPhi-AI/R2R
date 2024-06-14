"""Abstractions for documents and their extractions."""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
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
