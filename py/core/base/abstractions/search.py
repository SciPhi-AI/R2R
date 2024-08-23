"""Abstractions for search functionality."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .llm import GenerationConfig


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: Optional[UUID]
    group_ids: list[UUID]
    score: float
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"VectorSearchResult(fragment_id={self.fragment_id}, extraction_id={self.extraction_id}, document_id={self.document_id}, score={self.score})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "fragment_id": self.fragment_id,
            "extraction_id": self.extraction_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "group_ids": self.group_ids,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }

    class Config:
        json_schema_extra = {
            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
            "group_ids": [],
            "score": 0.23943702876567796,
            "text": "Example text from the document",
            "metadata": {
                "title": "example_document.pdf",
                "associatedQuery": "What is the capital of France?",
            },
        }


class KGLocalSearchResult(BaseModel):
    """Result of a local knowledge graph search operation."""

    query: str
    entities: dict[str, Any]
    relationships: dict[str, Any]
    communities: dict[str, Any]

    def __str__(self) -> str:
        return f"LocalSearchResult(query={self.query}, search_result={self.search_result})"

    def __repr__(self) -> str:
        return self.__str__()


class KGGlobalSearchResult(BaseModel):
    """Result of a global knowledge graph search operation."""

    query: str
    search_result: list[str]

    def __str__(self) -> str:
        return f"KGGlobalSearchResult(query={self.query}, search_result={self.search_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {"query": self.query, "search_result": self.search_result}


class KGSearchResult(BaseModel):
    """Result of a knowledge graph search operation."""

    local_result: Optional[KGLocalSearchResult] = None
    global_result: Optional[KGGlobalSearchResult] = None

    def __str__(self) -> str:
        return f"KGSearchResult(local_result={self.local_result}, global_result={self.global_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "local_result": (
                self.local_result.dict() if self.local_result else None
            ),
            "global_result": (
                self.global_result.dict() if self.global_result else None
            ),
        }


class AggregateSearchResult(BaseModel):
    """Result of an aggregate search operation."""

    vector_search_results: Optional[list[VectorSearchResult]]
    kg_search_results: Optional[list[KGSearchResult]] = None

    def __str__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def __repr__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def dict(self) -> dict:
        return {
            "vector_search_results": (
                [result.dict() for result in self.vector_search_results]
                if self.vector_search_results
                else []
            ),
            "kg_search_results": self.kg_search_results or None,
        }


# TODO - stop duplication of this enum, move collections primitives to 'abstractions'
class IndexMeasure(str, Enum):
    """
    An enum representing the types of distance measures available for indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    cosine_distance = "cosine_distance"
    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"


class HybridSearchSettings(BaseModel):
    full_text_weight: float = Field(
        default=1.0, description="Weight to apply to full text search"
    )
    semantic_weight: float = Field(
        default=5.0, description="Weight to apply to semantic search"
    )
    full_text_limit: int = Field(
        default=200,
        description="Maximum number of results to return from full text search",
    )
    rrf_k: int = Field(
        default=50, description="K-value for RRF (Rank Reciprocal Fusion)"
    )


class VectorSearchSettings(BaseModel):
    use_vector_search: bool = Field(
        default=True, description="Whether to use vector search"
    )
    use_hybrid_search: bool = Field(
        default=False,
        description="Whether to perform a hybrid search (combining vector and keyword search)",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the vector search",
    )
    search_limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=1_000,
    )
    selected_group_ids: list[UUID] = Field(
        default_factory=list,
        description="Group IDs to search for",
    )
    index_measure: IndexMeasure = Field(
        default=IndexMeasure.cosine_distance,
        description="The distance measure to use for indexing",
    )
    include_values: bool = Field(
        default=True,
        description="Whether to include search score values in the search results",
    )
    include_metadatas: bool = Field(
        default=True,
        description="Whether to include element metadata in the search results",
    )
    probes: Optional[int] = Field(
        default=10,
        description="Number of ivfflat index lists to query. Higher increases accuracy but decreases speed.",
    )
    ef_search: Optional[int] = Field(
        default=40,
        description="Size of the dynamic candidate list for HNSW index search. Higher increases accuracy but decreases speed.",
    )
    hybrid_search_settings: Optional[HybridSearchSettings] = Field(
        default=HybridSearchSettings(),
        description="Settings for hybrid search",
    )

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_vector_search": True,
            "use_hybrid_search": True,
            "filters": {"category": "technology"},
            "search_limit": 20,
            "selected_group_ids": [
                "2acb499e-8428-543b-bd85-0d9098718220",
                "3e157b3a-8469-51db-90d9-52e7d896b49b",
            ],
            "index_measure": "cosine_distance",
            "include_metadata": True,
            "probes": 10,
            "ef_search": 40,
            "hybrid_search_settings": {
                "full_text_weight": 1.0,
                "semantic_weight": 5.0,
                "full_text_limit": 200,
                "rrf_k": 50,
            },
        }

    def model_dump(self, *args, **kwargs):
        dump = super().model_dump(*args, **kwargs)
        dump["selected_group_ids"] = [
            str(uuid) for uuid in dump["selected_group_ids"]
        ]
        return dump


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    kg_search_type: str = "global"  # 'global' or 'local'
    kg_search_level: Optional[str] = None
    kg_search_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
    entity_types: list = []
    relationships: list = []
    max_community_description_length: int = 4096 * 4
    max_llm_queries_for_global_search: int = 250
    local_search_limits: dict[str, int] = {
        "__Entity__": 20,
        "__Relationship__": 20,
        "__Community__": 20,
    }

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_kg_search": True,
            "kg_search_type": "global",
            "kg_search_level": "global",
            "kg_search_generation_config": GenerationConfig.Config.json_schema_extra,
            "entity_types": ["Person", "Organization"],
            "relationships": ["founder", "CEO"],
            "max_community_description_length": 4096 * 4,
            "max_llm_queries_for_global_search": 250,
            "local_search_limits": {
                "__Entity__": 20,
                "__Relationship__": 20,
                "__Community__": 20,
            },
        }
