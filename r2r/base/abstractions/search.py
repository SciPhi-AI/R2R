"""Abstractions for search functionality."""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .llm import GenerationConfig


class VectorSearchSettings(BaseModel):
    use_vector_search: bool = True
    filters: dict[str, Any] = Field(default_factory=dict)
    search_limit: int = 10
    do_hybrid_search: bool = False


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    fragment_id: uuid.UUID
    extraction_id: uuid.UUID
    document_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    group_ids: List[uuid.UUID]
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


KGSearchResult = List[Tuple[str, List[Dict[str, Any]]]]


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    kg_search_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
    entity_types: list = []
    relationships: list = []


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
