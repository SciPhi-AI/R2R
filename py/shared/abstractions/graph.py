import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from pydantic import Field

from .base import R2RSerializable


class EntityType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class RelationshipType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class DataLevel(str, Enum):
    GRAPH = "graph"
    COLLECTION = "collection"
    DOCUMENT = "document"
    CHUNK = "chunk"

    def __str__(self):
        return self.value


class Entity(R2RSerializable):
    """An entity extracted from a document."""

    id: Optional[UUID | int] = (
        None  # id is Union of UUID and int for backwards compatibility
    )
    sid: Optional[int] = None  # deprecated, remove in the future
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    chunk_ids: list[UUID] = Field(
        alias="chunkIds",
        default_factory=list,
    )
    description_embedding: Optional[list[float] | str] = Field(
        alias="descriptionEmbedding",
        default=None,
    )
    document_id: Optional[UUID] = Field(  # this is for backward compatibility
        alias="documentId",
        default=None,
    )
    document_ids: list[UUID] = Field(
        alias="documentIds",
        default_factory=list,
    )
    graph_ids: list[UUID] = Field(
        alias="graphIds",
        default_factory=list,
    )
    user_id: UUID = Field(
        alias="userId",
    )
    last_modified_by: UUID = Field(
        alias="lastModifiedBy",
    )
    created_at: datetime = Field(
        alias="createdAt",
        default_factory=datetime.utcnow,
    )
    updated_at: datetime = Field(
        alias="updatedAt",
        default_factory=datetime.utcnow,
    )
    attributes: Optional[dict[str, Any] | str] = None

    def __str__(self):
        return (
            f"{self.category}:{self.subcategory}:{self.value}"
            if self.subcategory
            else f"{self.category}:{self.value}"
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.attributes, str):
            try:
                self.attributes = json.loads(self.attributes)
            except json.JSONDecodeError:
                self.attributes = self.attributes


class Relationship(R2RSerializable):
    """A relationship between two entities. This is a generic relationship, and can be used to represent any type of relationship between any two entities."""

    # id is Union of UUID and int for backwards compatibility
    subject: str
    predicate: str
    object: str
    id: Optional[UUID | int] = None
    subject_id: Optional[UUID] = None
    object_id: Optional[UUID] = None
    weight: float | None = 1.0
    description: str | None = None
    description_embedding: list[float] | None = None
    predicate_embedding: list[float] | None = None
    chunk_ids: list[UUID] = []
    document_id: Optional[UUID] = None
    graph_id: Optional[UUID] = None
    attributes: dict[str, Any] | str = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.attributes, str):
            try:
                self.attributes = json.loads(self.attributes)
            except json.JSONDecodeError:
                self.attributes = self.attributes


@dataclass
class CommunityInfo(R2RSerializable):
    """A protocol for a community in the system."""

    node: str
    cluster: int
    level: int
    id: Optional[UUID | int] = None
    parent_cluster: int | None
    is_final_cluster: bool
    graph_id: Optional[UUID] = None
    collection_id: Optional[UUID] = None  # for backwards compatibility
    relationship_ids: Optional[list[int]] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass
class Community(R2RSerializable):

    community_number: int
    level: int
    name: str = ""
    summary: str = ""

    findings: list[str] = []
    id: Optional[int | UUID] = None
    graph_ids: list[UUID] = []
    collection_id: Optional[UUID] = None
    rating: float | None = None
    rating_explanation: str | None = None
    embedding: list[float] | None = None
    attributes: dict[str, Any] | None = None

    def __init__(self, **kwargs):
        if isinstance(kwargs.get("attributes", None), str):
            kwargs["attributes"] = json.loads(kwargs["attributes"])

        if isinstance(kwargs.get("embedding", None), str):
            kwargs["embedding"] = json.loads(kwargs["embedding"])

        super().__init__(**kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "Community":
        parsed_data: dict[str, Any] = (
            json.loads(data) if isinstance(data, str) else data
        )
        if isinstance(parsed_data.get("embedding", None), str):
            parsed_data["embedding"] = json.loads(parsed_data["embedding"])
        return cls(**parsed_data)


class KGExtraction(R2RSerializable):
    """A protocol for a knowledge graph extraction."""

    chunk_ids: list[UUID]
    document_id: UUID
    entities: list[Entity]
    relationships: list[Relationship]


class Graph(R2RSerializable):
    id: UUID = Field(default=None)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(
        alias="createdAt",
        default_factory=datetime.utcnow,
    )
    updated_at: datetime = Field(
        alias="updatedAt",
        default_factory=datetime.utcnow,
    )
    statistics: dict[str, Any] = {}
    attributes: dict[str, Any] = {}
    status: str = "pending"

    class Config:
        populate_by_name = True
        from_attributes = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "Graph":
        """Create a Graph instance from a dictionary."""
        # Convert string to dict if needed
        parsed_data: dict[str, Any] = (
            json.loads(data) if isinstance(data, str) else data
        )

        # Convert string representations to dicts before validation
        if isinstance(parsed_data.get("attributes", {}), str):
            parsed_data["attributes"] = json.loads(parsed_data["attributes"])
        if isinstance(parsed_data.get("statistics", {}), str):
            parsed_data["statistics"] = json.loads(parsed_data["statistics"])
        return cls(**parsed_data)

    def __init__(self, **kwargs):
        # Convert string representations to dicts before calling super().__init__
        if isinstance(kwargs.get("attributes", {}), str):
            kwargs["attributes"] = json.loads(kwargs["attributes"])
        if isinstance(kwargs.get("statistics", {}), str):
            kwargs["statistics"] = json.loads(kwargs["statistics"])
        super().__init__(**kwargs)
