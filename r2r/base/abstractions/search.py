"""Abstractions for search functionality."""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .llm import GenerationConfig


class VectorSearchRequest(BaseModel):
    """Request for a search operation."""

    query: str
    limit: int
    filters: Optional[dict[str, Any]] = None


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    id: uuid.UUID
    score: float
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def dict(self) -> dict:
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }


class KGSearchRequest(BaseModel):
    """Request for a knowledge graph search operation."""

    query: str


# [query, ...]
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
    use_vector_search: bool = True
    search_filters: dict[str, Any] = Field(default_factory=dict)
    search_limit: int = 10
    do_hybrid_search: bool = False


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    agent_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
