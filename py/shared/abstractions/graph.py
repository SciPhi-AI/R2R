import json
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel

from .base import R2RSerializable

logger = logging.getLogger()


@dataclass
class Identified:
    """A protocol for an item with an ID."""

    id: str
    """The ID of the item."""

    short_id: str | None
    """Human readable ID used to refer to this community in prompts or texts displayed to users, such as in a report text (optional)."""


@dataclass
class Named(Identified):
    """A protocol for an item with a name/title."""

    title: str
    """The name/title of the item."""


class EntityType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class RelationshipType(R2RSerializable):
    id: str
    name: str
    description: str | None = None


class EntityLevel(str, Enum):
    COLLECTION = "collection"
    DOCUMENT = "document"
    CHUNK = "chunk"

    def __str__(self):
        return self.value


class Entity(R2RSerializable):
    """An entity extracted from a document."""

    name: str
    id: Optional[int] = None
    level: Optional[EntityLevel] = None
    category: Optional[str] = None
    description: Optional[str] = None
    description_embedding: Optional[Union[list[float], str]] = None
    community_numbers: Optional[list[str]] = None
    extraction_ids: Optional[list[UUID]] = None
    collection_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    document_ids: Optional[list[UUID]] = None
    # we don't use these yet
    # name_embedding: Optional[list[float]] = None
    # graph_embedding: Optional[list[float]] = None
    # rank: Optional[int] = None
    attributes: Optional[Union[dict[str, Any], str]] = None

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

    id: Optional[int] = None

    subject: str
    """The source entity name."""

    predicate: str
    """A description of the relationship (optional)."""

    object: str
    """The target entity name."""

    weight: float | None = 1.0
    """The edge weight."""

    description: str | None = None
    """A description of the relationship (optional)."""

    predicate_embedding: list[float] | None = None
    """The semantic embedding for the relationship description (optional)."""

    extraction_ids: list[UUID] = []
    """List of text unit IDs in which the relationship appears (optional)."""

    document_id: UUID | None = None
    """Document ID in which the relationship appears (optional)."""

    attributes: dict[str, Any] | str = {}
    """Additional attributes associated with the relationship (optional). To be included in the search prompt"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.attributes, str):
            try:
                self.attributes = json.loads(self.attributes)
            except json.JSONDecodeError:
                self.attributes = self.attributes

    @classmethod
    def from_dict(  # type: ignore
        cls,
        d: dict[str, Any],
        id_key: str = "id",
        short_id_key: str = "short_id",
        source_key: str = "subject",
        target_key: str = "object",
        predicate_key: str = "predicate",
        description_key: str = "description",
        weight_key: str = "weight",
        extraction_ids_key: str = "extraction_ids",
        document_id_key: str = "document_id",
        attributes_key: str = "attributes",
    ) -> "Relationship":
        """Create a new relationship from the dict data."""

        return Relationship(
            id=d[id_key],
            short_id=d.get(short_id_key),
            subject=d[source_key],
            object=d[target_key],
            predicate=d.get(predicate_key),
            description=d.get(description_key),
            weight=d.get(weight_key, 1.0),
            extraction_ids=d.get(extraction_ids_key),
            document_id=d.get(document_id_key),
            attributes=d.get(attributes_key, {}),
        )

@dataclass
class CommunityInfo(BaseModel):
    """A protocol for a community in the system."""

    node: str
    cluster: int
    parent_cluster: int | None
    level: int
    is_final_cluster: bool
    collection_id: uuid.UUID
    relationship_ids: Optional[list[int]] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CommunityInfo":
        return CommunityInfo(
            node=d["node"],
            cluster=d["cluster"],
            parent_cluster=d["parent_cluster"],
            level=d["level"],
            is_final_cluster=d["is_final_cluster"],
            relationship_ids=d["relationship_ids"],
            collection_id=d["collection_id"],
        )


@dataclass
class Community(BaseModel):
    """Defines an LLM-generated summary report of a community."""

    community_number: int
    """The ID of the community this report is associated with."""

    level: int
    """The level of the community this report is associated with."""

    collection_id: uuid.UUID
    """The ID of the collection this report is associated with."""

    name: str = ""
    """Name of the report."""

    summary: str = ""
    """Summary of the report."""

    findings: list[str] = []
    """Findings of the report."""

    rating: float | None = None
    """Rating of the report."""

    rating_explanation: str | None = None
    """Explanation of the rating."""

    embedding: list[float] | None = None
    """Embedding of summary and findings."""

    attributes: dict[str, Any] | None = None
    """A dictionary of additional attributes associated with the report (optional)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.attributes, str):
            self.attributes = json.loads(self.attributes)

    @classmethod
    def from_dict(
        cls,
        d: dict[str, Any],
        id_key: str = "id",
        title_key: str = "title",
        community_number_key: str = "community_number",
        short_id_key: str = "short_id",
        summary_key: str = "summary",
        findings_key: str = "findings",
        rank_key: str = "rank",
        summary_embedding_key: str = "summary_embedding",
        embedding_key: str = "embedding",
        attributes_key: str = "attributes",
    ) -> "Community":
        """Create a new community report from the dict data."""
        return Community(
            id=d[id_key],
            title=d[title_key],
            community_number=d[community_number_key],
            short_id=d.get(short_id_key),
            summary=d[summary_key],
            findings=d[findings_key],
            rank=d[rank_key],
            summary_embedding=d.get(summary_embedding_key),
            embedding=d.get(embedding_key),
            attributes=d.get(attributes_key),
        )


class KGExtraction(R2RSerializable):
    """An extraction from a document that is part of a knowledge graph."""

    extraction_ids: list[uuid.UUID]
    document_id: uuid.UUID
    entities: list[Entity]
    relationships: list[Relationship]
