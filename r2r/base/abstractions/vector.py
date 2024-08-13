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

    def __init__(
        self,
        fragment_id: UUID,
        extraction_id: UUID,
        document_id: UUID,
        user_id: UUID,
        group_ids: list[UUID],
        vector: Vector,
        text: str,
        metadata: dict[str, Any],
    ):
        """Create a new VectorEntry object."""
        self.fragment_id = fragment_id
        self.extraction_id = extraction_id
        self.document_id = document_id
        self.user_id = user_id
        self.group_ids = group_ids
        self.vector = vector
        self.text = text
        self.metadata = metadata

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return (
            f"VectorEntry(fragment_id={self.fragment_id}, "
            f"extraction_id={self.extraction_id}, "
            f"document_id={self.document_id}, "
            f"user_id={self.user_id}, "
            f"group_ids={self.group_ids}, "
            f"vector={self.vector}, "
            f"text={self.text}, "
            f"metadata={self.metadata})"
        )

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return self.__str__()
