"""Abstraction for a vector that can be stored in the system."""

from enum import Enum
from typing import Any
from uuid import UUID


class VectorType(Enum):
    FIXED = "FIXED"


class Vector:
    """A vector with the option to fix the number of elements."""

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
    """A vector entry that can be stored directly in supported vector databases."""

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
        return {
            "id": str(self.id),
            "vector": self.vector.data,
            "metadata": metadata,
        }

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return f"VectorEntry(id={self.id}, vector={self.vector}, metadata={self.metadata})"
