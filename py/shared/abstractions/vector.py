"""Abstraction for a vector that can be stored in the system."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from .base import R2RSerializable


class VectorType(str, Enum):
    FIXED = "FIXED"


class IndexMethod(str, Enum):
    """
    An enum representing the index methods available.

    This class currently only supports the 'ivfflat' method but may
    expand in the future.

    Attributes:
        auto (str): Automatically choose the best available index method.
        ivfflat (str): The ivfflat index method.
        hnsw (str): The hnsw index method.
    """

    auto = "auto"
    ivfflat = "ivfflat"
    hnsw = "hnsw"

    def __str__(self) -> str:
        return self.value


class IndexMeasure(str, Enum):
    """
    An enum representing the types of distance measures available for indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    cosine_distance = "cosine_distance"
    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"

    def __str__(self) -> str:
        return self.value


class IndexArgsIVFFlat(R2RSerializable):
    """
    A class for arguments that can optionally be supplied to the index creation
    method when building an IVFFlat type index.

    Attributes:
        nlist (int): The number of IVF centroids that the index should use
    """

    n_lists: int


class IndexArgsHNSW(R2RSerializable):
    """
    A class for arguments that can optionally be supplied to the index creation
    method when building an HNSW type index.

    Ref: https://github.com/pgvector/pgvector#index-options

    Both attributes are Optional in case the user only wants to specify one and
    leave the other as default

    Attributes:
        m (int): Maximum number of connections per node per layer (default: 16)
        ef_construction (int): Size of the dynamic candidate list for
            constructing the graph (default: 64)
    """

    m: Optional[int] = 16
    ef_construction: Optional[int] = 64


INDEX_MEASURE_TO_OPS = {
    # Maps the IndexMeasure enum options to the SQL ops string required by
    # the pgvector `create index` statement
    IndexMeasure.cosine_distance: "vector_cosine_ops",
    IndexMeasure.l2_distance: "vector_l2_ops",
    IndexMeasure.max_inner_product: "vector_ip_ops",
}

INDEX_MEASURE_TO_SQLA_ACC = {
    IndexMeasure.cosine_distance: lambda x: x.cosine_distance,
    IndexMeasure.l2_distance: lambda x: x.l2_distance,
    IndexMeasure.max_inner_product: lambda x: x.max_inner_product,
}


class VectorTableName(str, Enum):
    """
    This enum represents the different tables where we store vectors.

    # TODO: change the table name of the chunks table. Right now it is called
    # {r2r_project_name}.{r2r_project_name} due to a bug in the vector class.
    """

    CHUNKS = "CHUNKS"
    ENTITIES = "entity_embedding"
    # TODO: Add support for triples
    # TRIPLES = "triple_raw"
    COMMUNITIES = "community_report"

    def __str__(self) -> str:
        return self.value


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
            f"VectorEntry("
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
    document_id: UUID
    num_chunks: int = 0
    error_message: Optional[str] = None

    def __str__(self) -> str:
        """Return a string representation of the StorageResult."""
        return f"StorageResult(success={self.success}, error_message={self.error_message})"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the StorageResult."""
        return self.__str__()
