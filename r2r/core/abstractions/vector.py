import json
from enum import Enum
from typing import Any
from uuid import UUID


class VectorType(Enum):
    FIXED = "FIXED"


class Vector:
    def __init__(
        self,
        data: list[float],
        type: VectorType = VectorType.FIXED,
        length: int = -1,
    ):
        self.data = data
        self.type = type
        self.length = length

        if (
            self.type == VectorType.FIXED
            and length > 0
            and len(data) != length
        ):
            raise ValueError(f"Vector must be exactly {length} elements long.")

    def __repr__(self) -> str:
        return (
            f"Vector(data={self.data}, type={self.type}, length={self.length})"
        )


class VectorEntry:
    def __init__(self, id: UUID, vector: Vector, metadata: dict[str, Any]):
        """Create a new VectorEntry object."""
        self.vector = vector
        self.id = id
        self.metadata = metadata

    def to_serializable(self) -> str:
        """Return a serializable representation of the VectorEntry."""
        metadata = self.metadata

        for key in metadata:
            if isinstance(metadata[key], UUID):
                metadata[key] = str(metadata[key])
        return {"id": str(self.id), "vector": self.vector.data, "metadata": json.dumps(metadata)}

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"


class VectorSearchResult:
    def __init__(
        self, id: str, score: float, metadata: dict[str, Any]
    ) -> None:
        """Create a new VectorSearchResult object."""
        self.id = id
        self.score = score
        self.metadata = metadata

    def __str__(self) -> str:
        """Return a string representation of the VectorSearchResult."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorSearchResult for debugging."""
        return f"VectorSearchResult(id={self.id}, score={self.score}, metadata={self.metadata})"

    def dict(self) -> dict:
        """Return a dictionary representation of the VectorSearchResult."""
        return {
            "id": self.id,
            "score": self.score,
            "metadata": self.metadata,
        }
