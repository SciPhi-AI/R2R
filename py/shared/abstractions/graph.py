import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel

from .base import R2RSerializable

logger = logging.getLogger(__name__)


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


class Entity(R2RSerializable):
    """An entity extracted from a document."""

    name: str
    id: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    description_embedding: Optional[list[float]] = None
    community_numbers: Optional[list[str]] = None
    extraction_ids: Optional[list[UUID]] = None
    collection_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
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
                pass


class Triple(BaseModel):
    """A relationship between two entities. This is a generic relationship, and can be used to represent any type of relationship between any two entities."""

    id: Optional[int] = None

    subject: str | None = None
    """The source entity name."""

    predicate: str | None = None
    """A description of the relationship (optional)."""

    object: str | None = None
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
    def from_dict(
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
    ) -> "Triple":
        """Create a new relationship from the dict data."""

        return Triple(
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
class Community(BaseModel):
    """A protocol for a community in the system."""

    id: int | None = None
    """The ID of the community."""

    level: int | None = None
    """Community level."""

    entity_ids: list[str] | None = None
    """List of entity IDs related to the community (optional)."""

    relationship_ids: list[str] | None = None
    """List of relationship IDs related to the community (optional)."""

    covariate_ids: dict[str, list[str]] | None = None
    """Dictionary of different types of covariates related to the community (optional), e.g. claims"""

    attributes: dict[str, Any] | None = None
    """A dictionary of additional attributes associated with the community (optional). To be included in the search prompt."""

    summary: str = ""
    """Summary of the report."""

    full_content: str = ""
    """Full content of the report."""

    rank: float | None = 1.0
    """Rank of the report, used for sorting (optional). Higher means more important"""

    embedding: list[float] | None = None
    """The semantic (i.e. text) embedding of the report summary (optional)."""

    full_content_embedding: list[float] | None = None
    """The semantic (i.e. text) embedding of the full report content (optional)."""

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
        short_id_key: str = "short_id",
        level_key: str = "level",
        entities_key: str = "entity_ids",
        relationships_key: str = "relationship_ids",
        covariates_key: str = "covariate_ids",
        attributes_key: str = "attributes",
    ) -> "Community":
        """Create a new community from the dict data."""
        return Community(
            id=d[id_key],
            title=d[title_key],
            short_id=d.get(short_id_key),
            level=d[level_key],
            entity_ids=d.get(entities_key),
            relationship_ids=d.get(relationships_key),
            covariate_ids=d.get(covariates_key),
            attributes=d.get(attributes_key),
        )


@dataclass
class CommunityReport(BaseModel):
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
    ) -> "CommunityReport":
        """Create a new community report from the dict data."""
        return CommunityReport(
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
    triples: list[Triple]
