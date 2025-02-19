"""Abstraction for a vector that can be stored in the system."""

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .base import R2RSerializable


class VectorType(str, Enum):
    FIXED = "FIXED"


class IndexMethod(str, Enum):
    """An enum representing the index methods available.

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
    """An enum representing the types of distance measures available for
    indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"
    cosine_distance = "cosine_distance"
    l1_distance = "l1_distance"
    hamming_distance = "hamming_distance"
    jaccard_distance = "jaccard_distance"

    def __str__(self) -> str:
        return self.value

    @property
    def ops(self) -> str:
        return {
            IndexMeasure.l2_distance: "_l2_ops",
            IndexMeasure.max_inner_product: "_ip_ops",
            IndexMeasure.cosine_distance: "_cosine_ops",
            IndexMeasure.l1_distance: "_l1_ops",
            IndexMeasure.hamming_distance: "_hamming_ops",
            IndexMeasure.jaccard_distance: "_jaccard_ops",
        }[self]

    @property
    def pgvector_repr(self) -> str:
        return {
            IndexMeasure.l2_distance: "<->",
            IndexMeasure.max_inner_product: "<#>",
            IndexMeasure.cosine_distance: "<=>",
            IndexMeasure.l1_distance: "<+>",
            IndexMeasure.hamming_distance: "<~>",
            IndexMeasure.jaccard_distance: "<%>",
        }[self]


class IndexArgsIVFFlat(R2RSerializable):
    """A class for arguments that can optionally be supplied to the index
    creation method when building an IVFFlat type index.

    Attributes:
        nlist (int): The number of IVF centroids that the index should use
    """

    n_lists: int


class IndexArgsHNSW(R2RSerializable):
    """A class for arguments that can optionally be supplied to the index
    creation method when building an HNSW type index.

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


class VectorTableName(str, Enum):
    """This enum represents the different tables where we store vectors."""

    CHUNKS = "chunks"
    ENTITIES_DOCUMENT = "documents_entities"
    GRAPHS_ENTITIES = "graphs_entities"
    # TODO: Add support for relationships
    # TRIPLES = "relationship"
    COMMUNITIES = "graphs_communities"

    def __str__(self) -> str:
        return self.value


class VectorQuantizationType(str, Enum):
    """An enum representing the types of quantization available for vectors.

    Attributes:
        FP32 (str): 32-bit floating point quantization.
        FP16 (str): 16-bit floating point quantization.
        INT1 (str): 1-bit integer quantization.
        SPARSE (str): Sparse vector quantization.
    """

    FP32 = "FP32"
    FP16 = "FP16"
    INT1 = "INT1"
    SPARSE = "SPARSE"

    def __str__(self) -> str:
        return self.value

    @property
    def db_type(self) -> str:
        db_type_mapping = {
            "FP32": "vector",
            "FP16": "halfvec",
            "INT1": "bit",
            "SPARSE": "sparsevec",
        }
        return db_type_mapping[self.value]


class VectorQuantizationSettings(R2RSerializable):
    quantization_type: VectorQuantizationType = Field(
        default=VectorQuantizationType.FP32
    )


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
    """A vector entry that can be stored directly in supported vector
    databases."""

    id: UUID
    document_id: UUID
    owner_id: UUID
    collection_ids: list[UUID]
    vector: Vector
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        """Return a string representation of the VectorEntry."""
        return (
            f"VectorEntry("
            f"chunk_id={self.id}, "
            f"document_id={self.document_id}, "
            f"owner_id={self.owner_id}, "
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


class IndexConfig(BaseModel):
    name: Optional[str] = Field(default=None)
    table_name: Optional[str] = Field(default=VectorTableName.CHUNKS)
    index_method: Optional[str] = Field(default=IndexMethod.hnsw)
    index_measure: Optional[str] = Field(default=IndexMeasure.cosine_distance)
    index_arguments: Optional[IndexArgsIVFFlat | IndexArgsHNSW] = Field(
        default=None
    )
    index_name: Optional[str] = Field(default=None)
    index_column: Optional[str] = Field(default=None)
    concurrently: Optional[bool] = Field(default=True)
