import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from ..abstractions.llm import GenerationConfig
from .base import R2RSerializable


class Entity(R2RSerializable):
    """An entity extracted from a document."""

    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    id: Optional[UUID] = None
    parent_id: Optional[UUID] = None  # graph_id | document_id
    description_embedding: Optional[list[float] | str] = None
    chunk_ids: Optional[list[UUID]] = []

    def __str__(self):
        return f"{self.name}:{self.category}"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.metadata, str):
            try:
                self.metadata = json.loads(self.metadata)
            except json.JSONDecodeError:
                self.metadata = self.metadata


class Relationship(R2RSerializable):
    """A relationship between two entities.

    This is a generic relationship, and can be used to represent any type of
    relationship between any two entities.
    """

    id: Optional[UUID] = None
    subject: str
    predicate: str
    object: str
    description: Optional[str] = None
    subject_id: Optional[UUID] = None
    object_id: Optional[UUID] = None
    weight: float | None = 1.0
    chunk_ids: Optional[list[UUID]] = []
    parent_id: Optional[UUID] = None
    description_embedding: Optional[list[float] | str] = None
    metadata: Optional[dict[str, Any] | str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.metadata, str):
            try:
                self.metadata = json.loads(self.metadata)
            except json.JSONDecodeError:
                self.metadata = self.metadata


@dataclass
class Community(R2RSerializable):
    name: str = ""
    summary: str = ""
    level: Optional[int] = None
    findings: list[str] = []
    id: Optional[int | UUID] = None
    community_id: Optional[UUID] = None
    collection_id: Optional[UUID] = None
    rating: Optional[float] = None
    rating_explanation: Optional[str] = None
    description_embedding: Optional[list[float]] = None
    attributes: dict[str, Any] | None = None
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
    )

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


class GraphExtraction(R2RSerializable):
    """A protocol for a knowledge graph extraction."""

    entities: list[Entity]
    relationships: list[Relationship]


class Graph(R2RSerializable):
    id: UUID | None = Field()
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
    )
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
        return cls(**parsed_data)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class StoreType(str, Enum):
    GRAPHS = "graphs"
    DOCUMENTS = "documents"


class GraphCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    graph_extraction_prompt: str = Field(
        default="graph_extraction",
        description="The prompt to use for knowledge graph extraction.",
    )

    graph_entity_description_prompt: str = Field(
        default="graph_entity_description",
        description="The prompt to use for entity description generation.",
    )

    entity_types: list[str] = Field(
        default=[],
        description="The types of entities to extract.",
    )

    relation_types: list[str] = Field(
        default=[],
        description="The types of relations to extract.",
    )

    chunk_merge_count: int = Field(
        default=2,
        description="""The number of extractions to merge into a single graph
        extraction.""",
    )

    max_knowledge_relationships: int = Field(
        default=100,
        description="""The maximum number of knowledge relationships to extract
        from each chunk.""",
    )

    max_description_input_length: int = Field(
        default=65536,
        description="""The maximum length of the description for a node in the
        graph.""",
    )

    generation_config: Optional[GenerationConfig] = Field(
        default=None,
        description="Configuration for text generation during graph enrichment.",
    )

    automatic_deduplication: bool = Field(
        default=False,
        description="Whether to automatically deduplicate entities.",
    )


class GraphEnrichmentSettings(R2RSerializable):
    """Settings for knowledge graph enrichment."""

    force_graph_search_results_enrichment: bool = Field(
        default=False,
        description="""Force run the enrichment step even if graph creation is
        still in progress for some documents.""",
    )

    graph_communities_prompt: str = Field(
        default="graph_communities",
        description="The prompt to use for knowledge graph enrichment.",
    )

    max_summary_input_length: int = Field(
        default=65536,
        description="The maximum length of the summary for a community.",
    )

    generation_config: Optional[GenerationConfig] = Field(
        default=None,
        description="Configuration for text generation during graph enrichment.",
    )

    leiden_params: dict = Field(
        default_factory=dict,
        description="Parameters for the Leiden algorithm.",
    )


class GraphCommunitySettings(R2RSerializable):
    """Settings for knowledge graph community enrichment."""

    force_graph_search_results_enrichment: bool = Field(
        default=False,
        description="""Force run the enrichment step even if graph creation is
        still in progress for some documents.""",
    )

    graph_communities: str = Field(
        default="graph_communities",
        description="The prompt to use for knowledge graph enrichment.",
    )

    max_summary_input_length: int = Field(
        default=65536,
        description="The maximum length of the summary for a community.",
    )

    generation_config: Optional[GenerationConfig] = Field(
        default=None,
        description="Configuration for text generation during graph enrichment.",
    )

    leiden_params: dict = Field(
        default_factory=dict,
        description="Parameters for the Leiden algorithm.",
    )
