from typing import Any, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    limit: int
    filters: Optional[dict[str, Any]] = None


class SearchResult(BaseModel):
    id: str
    score: float
    metadata: dict[str, Any]

    def __str__(self) -> str:
        """Return a string representation of the SearchResult."""
        return f"SearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the SearchResult for debugging."""
        return f"SearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def dict(self) -> dict:
        """Return a dictionary representation of the SearchResult."""
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }
