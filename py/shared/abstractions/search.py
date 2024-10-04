"""Abstractions for search functionality."""

from enum import Enum
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class VectorSearchResult(R2RSerializable):
    """Result of a search operation."""

    extraction_id: UUID
    document_id: UUID
    user_id: Optional[UUID]
    collection_ids: list[UUID]
    score: float
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"VectorSearchResult(id={self.extraction_id}, document_id={self.document_id}, score={self.score})"

    def __repr__(self) -> str:
        return self.__str__()

    def as_dict(self) -> dict:
        return {
            "extraction_id": self.extraction_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "collection_ids": self.collection_ids,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }

    class Config:
        json_schema_extra = {
            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
            "collection_ids": [],
            "score": 0.23943702876567796,
            "text": "Example text from the document",
            "metadata": {
                "title": "example_document.pdf",
                "associated_query": "What is the capital of France?",
            },
        }


class KGSearchResultType(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    COMMUNITY = "community"


class KGSearchMethod(str, Enum):
    LOCAL = "local"
    GLOBAL = "global"


class KGEntityResult(R2RSerializable):
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Entity Name",
            "description": "Entity Description",
            "metadata": {},
        }


class KGRelationshipResult(R2RSerializable):
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Relationship Name",
            "description": "Relationship Description",
            "metadata": {},
        }


class KGCommunityResult(R2RSerializable):
    name: str
    summary: str
    rating: float
    rating_explanation: str
    findings: list[str]
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Community Name",
            "summary": "Community Summary",
            "rating": 9,
            "rating_explanation": "Rating Explanation",
            "findings": ["Finding 1", "Finding 2"],
            "metadata": {},
        }


class KGGlobalResult(R2RSerializable):
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Global Result Name",
            "description": "Global Result Description",
            "metadata": {},
        }


class KGSearchResult(R2RSerializable):
    method: KGSearchMethod
    content: Union[
        KGEntityResult, KGRelationshipResult, KGCommunityResult, KGGlobalResult
    ]
    result_type: Optional[KGSearchResultType] = None
    extraction_ids: Optional[list[UUID]] = None
    metadata: dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "method": "local",
            "content": KGEntityResult.Config.json_schema_extra,
            "result_type": "entity",
            "extraction_ids": ["c68dc72e-fc23-5452-8f49-d7bd46088a96"],
            "metadata": {"associated_query": "What is the capital of France?"},
        }


class AggregateSearchResult(R2RSerializable):
    """Result of an aggregate search operation."""

    vector_search_results: Optional[list[VectorSearchResult]]
    kg_search_results: Optional[list[KGSearchResult]] = None

    def __str__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def __repr__(self) -> str:
        return f"AggregateSearchResult(vector_search_results={self.vector_search_results}, kg_search_results={self.kg_search_results})"

    def as_dict(self) -> dict:
        return {
            "vector_search_results": (
                [result.as_dict() for result in self.vector_search_results]
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


class HybridSearchSettings(R2RSerializable):
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


class VectorSearchSettings(R2RSerializable):
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
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset to paginate search results",
    )
    selected_collection_ids: list[UUID] = Field(
        default_factory=list,
        description="Collection IDs to search for",
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
    search_strategy: str = Field(
        default="vanilla",
        description="Search strategy to use (e.g., 'default', 'query_fusion', 'hyde')",
    )

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_vector_search": True,
            "use_hybrid_search": True,
            "filters": {"category": "technology"},
            "limit": 20,
            "offset": 0,
            "selected_collection_ids": [
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
        dump["selected_collection_ids"] = [
            str(uuid) for uuid in dump["selected_collection_ids"]
        ]
        return dump


class KGSearchSettings(R2RSerializable):

    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the KG search",
    )

    selected_collection_ids: list[UUID] = Field(
        default_factory=list,
        description="Collection IDs to search for",
    )

    graphrag_map_system_prompt: str = Field(
        default="graphrag_map_system_prompt",
        description="The system prompt for the graphrag map prompt.",
    )

    graphrag_reduce_system_prompt: str = Field(
        default="graphrag_reduce_system_prompt",
        description="The system prompt for the graphrag reduce prompt.",
    )

    use_kg_search: bool = Field(
        default=False, description="Whether to use KG search"
    )
    kg_search_type: str = Field(
        default="local", description="KG search type"
    )  # 'global' or 'local'
    kg_search_level: Optional[str] = Field(
        default=None, description="KG search level"
    )
    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph search.",
    )

    # TODO: add these back in
    # entity_types: list = []
    # relationships: list = []
    max_community_description_length: int = 65536
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
            "kg_search_level": "0",
            "generation_config": GenerationConfig.Config.json_schema_extra,
            "max_community_description_length": 65536,
            "max_llm_queries_for_global_search": 250,
            "local_search_limits": {
                "__Entity__": 20,
                "__Relationship__": 20,
                "__Community__": 20,
            },
        }
