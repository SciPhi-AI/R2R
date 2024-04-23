import json
from typing import Any
from uuid import UUID


class VectorEntry:
    def __init__(
        self, entry_id: UUID, vector: list[float], metadata: dict[str, Any]
    ):
        """Create a new VectorEntry object."""
        self.vector = vector
        self.id = entry_id
        self.metadata = metadata

    def to_json(self) -> str:
        """Serialize the object to a JSON string."""
        return json.dumps(
            {"id": self.id, "vector": self.vector, "metadata": self.metadata},
            default=lambda o: o.__dict__,
        )

    @staticmethod
    def from_json(json_str: str) -> "VectorEntry":
        """Deserialize a JSON string into a VectorEntry object."""
        data = json.loads(json_str)
        return VectorEntry(
            vector=data["vector"],
            entry_id=data["id"],
            metadata=data["metadata"],
        )

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"


class VectorSearchResult:
    def __init__(
        self, entry_id: str, score: float, metadata: dict[str, Any]
    ) -> None:
        """Create a new VectorSearchResult object."""
        self.id = entry_id
        self.score = score
        self.metadata = metadata

    def __str__(self) -> str:
        """Return a string representation of the VectorSearchResult."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorSearchResult for debugging."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def to_dict(self) -> dict:
        """Return a dictionary representation of the VectorSearchResult."""
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }
