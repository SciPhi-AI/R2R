# abstractions are taken from LlamaIndex
# https://github.com/run-llama/llama_index
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, StrictFloat, StrictInt, StrictStr


class LabelledNode(BaseModel):
    """An entity in a graph."""

    label: str = Field(default="node", description="The label of the node.")
    embedding: Optional[List[float]] = Field(
        default=None, description="The embeddings of the node."
    )
    properties: Dict[str, Any] = Field(default_factory=dict)

    @abstractmethod
    def __str__(self) -> str:
        """Return the string representation of the node."""
        ...

    @property
    @abstractmethod
    def id(self) -> str:
        """Get the node id."""
        ...


class EntityNode(LabelledNode):
    """An entity in a graph."""

    name: str = Field(description="The name of the entity.")
    label: str = Field(default="entity", description="The label of the node.")
    properties: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        """Return the string representation of the node."""
        return self.name

    @property
    def id(self) -> str:
        """Get the node id."""
        return self.name.replace('"', " ")


class ChunkNode(LabelledNode):
    """A text chunk in a graph."""

    text: str = Field(description="The text content of the chunk.")
    id_: Optional[str] = Field(
        default=None,
        description="The id of the node. Defaults to a hash of the text.",
    )
    label: str = Field(
        default="text_chunk", description="The label of the node."
    )
    properties: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        """Return the string representation of the node."""
        return self.text

    @property
    def id(self) -> str:
        """Get the node id."""
        return str(hash(self.text)) if self.id_ is None else self.id_


class Relation(BaseModel):
    """A relation connecting two entities in a graph."""

    label: str
    source_id: str
    target_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        """Return the string representation of the relation."""
        return self.label

    @property
    def id(self) -> str:
        """Get the relation id."""
        return self.label


Triplet = Tuple[LabelledNode, Relation, LabelledNode]


class VectorStoreQueryMode(str, Enum):
    """Vector store query mode."""

    DEFAULT = "default"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    TEXT_SEARCH = "text_search"
    SEMANTIC_HYBRID = "semantic_hybrid"

    # fit learners
    SVM = "svm"
    LOGISTIC_REGRESSION = "logistic_regression"
    LINEAR_REGRESSION = "linear_regression"

    # maximum marginal relevance
    MMR = "mmr"


class FilterOperator(str, Enum):
    """Vector store filter operator."""

    # TODO add more operators
    EQ = "=="  # default operator (string, int, float)
    GT = ">"  # greater than (int, float)
    LT = "<"  # less than (int, float)
    NE = "!="  # not equal to (string, int, float)
    GTE = ">="  # greater than or equal to (int, float)
    LTE = "<="  # less than or equal to (int, float)
    IN = "in"  # In array (string or number)
    NIN = "nin"  # Not in array (string or number)
    ANY = "any"  # Contains any (array of strings)
    ALL = "all"  # Contains all (array of strings)
    TEXT_MATCH = "text_match"  # full text match (allows you to search for a specific substring, token or phrase within the text field)
    CONTAINS = "contains"  # metadata array contains value (string or number)


class MetadataFilter(BaseModel):
    """Comprehensive metadata filter for vector stores to support more operators.

    Value uses Strict* types, as int, float and str are compatible types and were all
    converted to string before.

    See: https://docs.pydantic.dev/latest/usage/types/#strict-types
    """

    key: str
    value: Union[
        StrictInt,
        StrictFloat,
        StrictStr,
        List[StrictStr],
        List[StrictFloat],
        List[StrictInt],
    ]
    operator: FilterOperator = FilterOperator.EQ

    @classmethod
    def from_dict(
        cls,
        filter_dict: Dict,
    ) -> "MetadataFilter":
        """Create MetadataFilter from dictionary.

        Args:
            filter_dict: Dict with key, value and operator.

        """
        return MetadataFilter.parse_obj(filter_dict)


# # TODO: Deprecate ExactMatchFilter and use MetadataFilter instead
# # Keep class for now so that AutoRetriever can still work with old vector stores
# class ExactMatchFilter(BaseModel):
#     key: str
#     value: Union[StrictInt, StrictFloat, StrictStr]

# set ExactMatchFilter to MetadataFilter
ExactMatchFilter = MetadataFilter


class FilterCondition(str, Enum):
    """Vector store filter conditions to combine different filters."""

    # TODO add more conditions
    AND = "and"
    OR = "or"


class MetadataFilters(BaseModel):
    """Metadata filters for vector stores."""

    # Exact match filters and Advanced filters with operators like >, <, >=, <=, !=, etc.
    filters: List[Union[MetadataFilter, ExactMatchFilter, "MetadataFilters"]]
    # and/or such conditions for combining different filters
    condition: Optional[FilterCondition] = FilterCondition.AND


@dataclass
class VectorStoreQuery:
    """Vector store query."""

    query_embedding: Optional[List[float]] = None
    similarity_top_k: int = 1
    doc_ids: Optional[List[str]] = None
    node_ids: Optional[List[str]] = None
    query_str: Optional[str] = None
    output_fields: Optional[List[str]] = None
    embedding_field: Optional[str] = None

    mode: VectorStoreQueryMode = VectorStoreQueryMode.DEFAULT

    # NOTE: only for hybrid search (0 for bm25, 1 for vector search)
    alpha: Optional[float] = None

    # metadata filters
    filters: Optional[MetadataFilters] = None

    # only for mmr
    mmr_threshold: Optional[float] = None

    # NOTE: currently only used by postgres hybrid search
    sparse_top_k: Optional[int] = None
    # NOTE: return top k results from hybrid search. similarity_top_k is used for dense search top k
    hybrid_top_k: Optional[int] = None


class PropertyGraphStore(ABC):
    """Abstract labelled graph store protocol.

    This protocol defines the interface for a graph store, which is responsible
    for storing and retrieving knowledge graph data.

    Attributes:
        client: Any: The client used to connect to the graph store.
        get: Callable[[str], List[List[str]]]: Get triplets for a given subject.
        get_rel_map: Callable[[Optional[List[str]], int], Dict[str, List[List[str]]]]:
            Get subjects' rel map in max depth.
        upsert_triplet: Callable[[str, str, str], None]: Upsert a triplet.
        delete: Callable[[str, str, str], None]: Delete a triplet.
        persist: Callable[[str, Optional[fsspec.AbstractFileSystem]], None]:
            Persist the graph store to a file.
    """

    supports_structured_queries: bool = False
    supports_vector_queries: bool = False

    @property
    def client(self) -> Any:
        """Get client."""
        ...

    @abstractmethod
    def get(
        self,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[LabelledNode]:
        """Get nodes with matching values."""
        ...

    @abstractmethod
    def get_triplets(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[Triplet]:
        """Get triplets with matching values."""
        ...

    @abstractmethod
    def get_rel_map(
        self,
        graph_nodes: List[LabelledNode],
        depth: int = 2,
        limit: int = 30,
        ignore_rels: Optional[List[str]] = None,
    ) -> List[Triplet]:
        """Get depth-aware rel map."""
        ...

    @abstractmethod
    def upsert_nodes(self, nodes: List[LabelledNode]) -> None:
        """Upsert nodes."""
        ...

    @abstractmethod
    def upsert_relations(self, relations: List[Relation]) -> None:
        """Upsert relations."""
        ...

    @abstractmethod
    def delete(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Delete matching data."""
        ...

    @abstractmethod
    def structured_query(
        self, query: str, param_map: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Query the graph store with statement and parameters."""
        ...

    @abstractmethod
    def vector_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> Tuple[List[LabelledNode], List[float]]:
        """Query the graph store with a vector store query."""
        ...

    # def persist(
    #     self, persist_path: str, fs: Optional[fsspec.AbstractFileSystem] = None
    # ) -> None:
    #     """Persist the graph store to a file."""
    #     return

    def get_schema(self, refresh: bool = False) -> Any:
        """Get the schema of the graph store."""
        return None

    def get_schema_str(self, refresh: bool = False) -> str:
        """Get the schema of the graph store as a string."""
        return str(self.get_schema(refresh=refresh))

    ### ----- Async Methods ----- ###

    async def aget(
        self,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[LabelledNode]:
        """Asynchronously get nodes with matching values."""
        return self.get(properties, ids)

    async def aget_triplets(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[Triplet]:
        """Asynchronously get triplets with matching values."""
        return self.get_triplets(entity_names, relation_names, properties, ids)

    async def aget_rel_map(
        self,
        graph_nodes: List[LabelledNode],
        depth: int = 2,
        limit: int = 30,
        ignore_rels: Optional[List[str]] = None,
    ) -> List[Triplet]:
        """Asynchronously get depth-aware rel map."""
        return self.get_rel_map(graph_nodes, depth, limit, ignore_rels)

    async def aupsert_nodes(self, nodes: List[LabelledNode]) -> None:
        """Asynchronously add nodes."""
        return self.upsert_nodes(nodes)

    async def aupsert_relations(self, relations: List[Relation]) -> None:
        """Asynchronously add relations."""
        return self.upsert_relations(relations)

    async def adelete(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Asynchronously delete matching data."""
        return self.delete(entity_names, relation_names, properties, ids)

    async def astructured_query(
        self, query: str, param_map: Optional[Dict[str, Any]] = {}
    ) -> Any:
        """Asynchronously query the graph store with statement and parameters."""
        return self.structured_query(query, param_map)

    async def avector_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> Tuple[List[LabelledNode], List[float]]:
        """Asynchronously query the graph store with a vector store query."""
        return self.vector_query(query, **kwargs)

    async def aget_schema(self, refresh: bool = False) -> str:
        """Asynchronously get the schema of the graph store."""
        return self.get_schema(refresh=refresh)

    async def aget_schema_str(self, refresh: bool = False) -> str:
        """Asynchronously get the schema of the graph store as a string."""
        return str(await self.aget_schema(refresh=refresh))


LIST_LIMIT = 128


def clean_string_values(text: str) -> str:
    return text.replace("\n", " ").replace("\r", " ")


def value_sanitize(d: Any) -> Any:
    """Sanitize the input dictionary or list.

    Sanitizes the input by removing embedding-like values,
    lists with more than 128 elements, that are mostly irrelevant for
    generating answers in a LLM context. These properties, if left in
    results, can occupy significant context space and detract from
    the LLM's performance by introducing unnecessary noise and cost.
    """
    if isinstance(d, dict):
        new_dict = {}
        for key, value in d.items():
            if isinstance(value, dict):
                sanitized_value = value_sanitize(value)
                if (
                    sanitized_value is not None
                ):  # Check if the sanitized value is not None
                    new_dict[key] = sanitized_value
            elif isinstance(value, list):
                if len(value) < LIST_LIMIT:
                    sanitized_value = value_sanitize(value)
                    if (
                        sanitized_value is not None
                    ):  # Check if the sanitized value is not None
                        new_dict[key] = sanitized_value
                # Do not include the key if the list is oversized
            else:
                new_dict[key] = value
        return new_dict
    elif isinstance(d, list):
        if len(d) < LIST_LIMIT:
            return [
                value_sanitize(item)
                for item in d
                if value_sanitize(item) is not None
            ]
        else:
            return None
    else:
        return d
