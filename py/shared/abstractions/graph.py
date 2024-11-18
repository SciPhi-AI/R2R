import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID
from datetime import datetime

from .base import R2RSerializable


class EntityType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class RelationshipType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class EntityLevel(str, Enum):
    GRAPH = "graph"
    COLLECTION = "collection"
    DOCUMENT = "document"
    CHUNK = "chunk"

    def __str__(self):
        return self.value


class Entity(R2RSerializable):
    """An entity extracted from a document."""

    id: UUID
    document_id: UUID
    name: str
    level: Optional[EntityLevel] = None
    category: Optional[str] = None
    description: Optional[str] = None
    description_embedding: Optional[list[float] | str] = None
    community_numbers: Optional[list[str]] = None
    chunk_ids: Optional[list[UUID]] = None
    graph_id: Optional[UUID] = None
    graph_ids: Optional[list[UUID]] = None
    document_id: Optional[UUID] = None
    document_ids: Optional[list[UUID]] = None

    # we don't use these yet
    # name_embedding: Optional[list[float]] = None
    # graph_embedding: Optional[list[float]] = None
    # rank: Optional[int] = None
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

    id: UUID
    document_id: UUID
    subject: Optional[str] = None
    predicate: Optional[str] = None
    subject_id: Optional[UUID] = None
    object_id: Optional[UUID] = None
    object: Optional[str] = None
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

    graph_id: UUID
    node: str
    cluster: int
    parent_cluster: int | None
    level: int
    is_final_cluster: bool
    graph_id: UUID
    relationship_ids: Optional[list[int]] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass
class Community(R2RSerializable):

    community_number: int
    level: int
    graph_id: UUID
    name: str = ""
    summary: str = ""
    findings: list[str] = []
    id: Optional[int | UUID] = None
    rating: float | None = None
    rating_explanation: str | None = None
    embedding: list[float] | None = None
    attributes: dict[str, Any] | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.attributes, str):
            self.attributes = json.loads(self.attributes)


class KGExtraction(R2RSerializable):
    """A protocol for a knowledge graph extraction."""

    chunk_ids: list[UUID]
    document_id: UUID
    entities: list[Entity]
    relationships: list[Relationship]


class Graph(R2RSerializable):
    """A request to create a graph."""

    name: str
    description: str
    statistics: dict[str, Any] = {}
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    attributes: dict[str, Any] = {}
    status: str = "pending"
    id: Optional[uuid.UUID] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'Graph':
        """Create a Graph instance from a dictionary."""
        # Convert string representations to dicts before validation
        if isinstance(data.get('attributes', {}), str):
            data['attributes'] = json.loads(data['attributes'])
        if isinstance(data.get('statistics', {}), str):
            data['statistics'] = json.loads(data['statistics'])
        return cls(**data)

    def __init__(self, **kwargs):
        # Convert string representations to dicts before calling super().__init__
        if isinstance(kwargs.get('attributes', {}), str):
            kwargs['attributes'] = json.loads(kwargs['attributes'])
        if isinstance(kwargs.get('statistics', {}), str):
            kwargs['statistics'] = json.loads(kwargs['statistics'])
        super().__init__(**kwargs)
