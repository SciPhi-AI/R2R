"""Abstractions for search functionality."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

from .llm import GenerationConfig


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    group_ids: List[UUID]
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
        schema_extra = [
            {
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
        ]


KGSearchResult = List[Tuple[str, List[Dict[str, Any]]]]


class AggregateSearchResult(BaseModel):
    """Result of an aggregate search operation."""

    vector_search_results: Optional[List[VectorSearchResult]]
    kg_search_results: Optional[KGSearchResult] = None

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
            "kg_search_results": self.kg_search_results or [],
        }


class VectorSearchSettings(BaseModel):
    use_vector_search: bool = Field(
        default=True, description="Whether to use vector search"
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the vector search",
    )
    search_limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=100,
    )
    do_hybrid_search: bool = Field(
        default=False,
        description="Whether to perform a hybrid search (combining vector and keyword search)",
    )


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    kg_search_type: str = "global"  # 'global' or 'local'
    kg_search_level: Optional[int] = None
    kg_search_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
    entity_types: list = []
    relationships: list = []
    max_community_description_length: int = 4096 * 4
    max_llm_queries_for_global_search: int = 10
    local_search_limits: dict[str, int] = {
        "__Entity__": 10,
        "__Relationship__": 10,
        "__Community__": 10,
    }
