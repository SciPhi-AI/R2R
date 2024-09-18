"""Abstraction for a vector that can be stored in the system."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from .base import R2RSerializable


class VectorType(Enum):
    FIXED = "FIXED"


class Vector(R2RSerializable):
    """A vector with the option to fix the number of elements."""

    data: list[float]
    type: VectorType = Field(default=VectorType.FIXED)
    length: int = Field(default=-1)

    def __init__(self, **data):
        super().__init__(**data)
        if (
            self.type == VectorType.FIXED
            and self.length > 0
            and len(self.data) != self.length
        ):
            raise ValueError(
                f"Vector must be exactly {self.length} elements long."
            )

    def __repr__(self) -> str:
        return (
            f"Vector(data={self.data}, type={self.type}, length={self.length})"
        )


class VectorEntry(R2RSerializable):
    """A vector entry that can be stored directly in supported vector databases."""

    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    vector: Vector
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return (
            f"VectorEntry(fragment_id={self.fragment_id}, "
            f"extraction_id={self.extraction_id}, "
            f"document_id={self.document_id}, "
            f"user_id={self.user_id}, "
            f"collection_ids={self.collection_ids}, "
            f"vector={self.vector}, "
            f"text={self.text}, "
            f"metadata={self.metadata})"
        )

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the VectorEntry."""
        return self.__str__()


class StorageResult(R2RSerializable):
    """A result of a storage operation."""

    success: bool
    document_id: UUID = None
    num_chunks: int = 0
    error_message: Optional[str] = None

    def __str__(self) -> str:
        """Return a string representation of the StorageResult."""
        return f"StorageResult(success={self.success}, error_message={self.error_message})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the StorageResult."""
        return self.__str__()
