"""Abstractions for search functionality."""

import uuid
from typing import Any, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    """Request for a search operation."""

    query: str
    limit: int
    filters: Optional[dict[str, Any]] = None


class SearchResult(BaseModel):
    """Result of a search operation."""

    id: uuid.UUID
    score: float
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"SearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        return f"SearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def dict(self) -> dict:
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }
