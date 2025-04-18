"""Abstractions for search functionality."""

from copy import copy
from enum import Enum
from typing import Any, Optional, Set
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import Field

from .base import R2RSerializable
from .document import DocumentResponse
from .llm import GenerationConfig
from .vector import IndexMeasure


def generate_id_from_label(label) -> UUID:
    return uuid5(NAMESPACE_DNS, label)


class ChunkSearchResult(R2RSerializable):
    """Result of a search operation."""

    id: UUID
    document_id: UUID
    owner_id: Optional[UUID]
    collection_ids: list[UUID]
    score: Optional[float] = None
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        if self.score:
            return (
                f"ChunkSearchResult(score={self.score:.3f}, text={self.text})"
            )
        else:
            return f"ChunkSearchResult(text={self.text})"

    def __repr__(self) -> str:
        return self.__str__()

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "owner_id": self.owner_id,
            "collection_ids": self.collection_ids,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                "owner_id": "2acb499e-8428-543b-bd85-0d9098718220",
                "collection_ids": [],
                "score": 0.23943702876567796,
                "text": "Example text from the document",
                "metadata": {
                    "title": "example_document.pdf",
                    "associated_query": "What is the capital of France?",
                },
            }
        }


class GraphSearchResultType(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    COMMUNITY = "community"


class GraphEntityResult(R2RSerializable):
    id: Optional[UUID] = None
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Entity Name",
                "description": "Entity Description",
                "metadata": {},
            }
        }


class GraphRelationshipResult(R2RSerializable):
    id: Optional[UUID] = None
    subject: str
    predicate: str
    object: str
    subject_id: Optional[UUID] = None
    object_id: Optional[UUID] = None
    metadata: Optional[dict[str, Any]] = None
    score: Optional[float] = None
    description: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Relationship Name",
                "description": "Relationship Description",
                "metadata": {},
            }
        }

    def __str__(self) -> str:
        return f"GraphRelationshipResult(subject={self.subject}, predicate={self.predicate}, object={self.object})"


class GraphCommunityResult(R2RSerializable):
    id: Optional[UUID] = None
    name: str
    summary: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Community Name",
                "summary": "Community Summary",
                "rating": 9,
                "rating_explanation": "Rating Explanation",
                "metadata": {},
            }
        }

    def __str__(self) -> str:
        return (
            f"GraphCommunityResult(name={self.name}, summary={self.summary})"
        )


class GraphSearchResult(R2RSerializable):
    content: GraphEntityResult | GraphRelationshipResult | GraphCommunityResult
    result_type: Optional[GraphSearchResultType] = None
    chunk_ids: Optional[list[UUID]] = None
    metadata: dict[str, Any] = {}
    score: Optional[float] = None
    id: UUID

    def __str__(self) -> str:
        return f"GraphSearchResult(content={self.content}, result_type={self.result_type})"

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "content": {
                    "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                    "name": "Entity Name",
                    "description": "Entity Description",
                    "metadata": {},
                },
                "result_type": "entity",
                "chunk_ids": ["c68dc72e-fc23-5452-8f49-d7bd46088a96"],
                "metadata": {
                    "associated_query": "What is the capital of France?"
                },
            }
        }


class WebPageSearchResult(R2RSerializable):
    title: Optional[str] = None
    link: Optional[str] = None
    snippet: Optional[str] = None
    position: int
    type: str = "organic"
    date: Optional[str] = None
    sitelinks: Optional[list[dict]] = None
    id: UUID

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Page Title",
                "link": "https://example.com/page",
                "snippet": "Page snippet",
                "position": 1,
                "date": "2021-01-01",
                "sitelinks": [
                    {
                        "title": "Sitelink Title",
                        "link": "https://example.com/sitelink",
                    }
                ],
            }
        }

    def __str__(self) -> str:
        return f"WebPageSearchResult(title={self.title}, link={self.link}, snippet={self.snippet})"


class RelatedSearchResult(R2RSerializable):
    query: str
    type: str = "related"
    id: UUID


class PeopleAlsoAskResult(R2RSerializable):
    question: str
    snippet: str
    link: str
    title: str
    id: UUID
    type: str = "peopleAlsoAsk"


class WebSearchResult(R2RSerializable):
    organic_results: list[WebPageSearchResult] = []
    related_searches: list[RelatedSearchResult] = []
    people_also_ask: list[PeopleAlsoAskResult] = []

    @classmethod
    def from_serper_results(cls, results: list[dict]) -> "WebSearchResult":
        organic = []
        related = []
        paa = []

        for result in results:
            if result["type"] == "organic":
                organic.append(
                    WebPageSearchResult(
                        **result, id=generate_id_from_label(result.get("link"))
                    )
                )
            elif result["type"] == "relatedSearches":
                related.append(
                    RelatedSearchResult(
                        **result,
                        id=generate_id_from_label(result.get("query")),
                    )
                )
            elif result["type"] == "peopleAlsoAsk":
                paa.append(
                    PeopleAlsoAskResult(
                        **result, id=generate_id_from_label(result.get("link"))
                    )
                )

        return cls(
            organic_results=organic,
            related_searches=related,
            people_also_ask=paa,
        )


class AggregateSearchResult(R2RSerializable):
    """Result of an aggregate search operation."""

    chunk_search_results: Optional[list[ChunkSearchResult]] = None
    graph_search_results: Optional[list[GraphSearchResult]] = None
    web_search_results: Optional[list[WebPageSearchResult]] = None
    document_search_results: Optional[list[DocumentResponse]] = None

    def __str__(self) -> str:
        return f"AggregateSearchResult(chunk_search_results={self.chunk_search_results}, graph_search_results={self.graph_search_results}, web_search_results={self.web_search_results}, document_search_results={str(self.document_search_results)})"

    def __repr__(self) -> str:
        return f"AggregateSearchResult(chunk_search_results={self.chunk_search_results}, graph_search_results={self.graph_search_results}, web_search_results={self.web_search_results}, document_search_results={str(self.document_search_results)})"

    def as_dict(self) -> dict:
        return {
            "chunk_search_results": (
                [result.as_dict() for result in self.chunk_search_results]
                if self.chunk_search_results
                else []
            ),
            "graph_search_results": (
                [result.to_dict() for result in self.graph_search_results]
                if self.graph_search_results
                else []
            ),
            "web_search_results": (
                [result.to_dict() for result in self.web_search_results]
                if self.web_search_results
                else []
            ),
            "document_search_results": (
                [cdr.to_dict() for cdr in self.document_search_results]
                if self.document_search_results
                else []
            ),
        }

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "chunk_search_results": [
                    {
                        "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                        "owner_id": "2acb499e-8428-543b-bd85-0d9098718220",
                        "collection_ids": [],
                        "score": 0.23943702876567796,
                        "text": "Example text from the document",
                        "metadata": {
                            "title": "example_document.pdf",
                            "associated_query": "What is the capital of France?",
                        },
                    }
                ],
                "graph_search_results": [
                    {
                        "content": {
                            "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                            "name": "Entity Name",
                            "description": "Entity Description",
                            "metadata": {},
                        },
                        "result_type": "entity",
                        "chunk_ids": ["c68dc72e-fc23-5452-8f49-d7bd46088a96"],
                        "metadata": {
                            "associated_query": "What is the capital of France?"
                        },
                    }
                ],
                "web_search_results": [
                    {
                        "title": "Page Title",
                        "link": "https://example.com/page",
                        "snippet": "Page snippet",
                        "position": 1,
                        "date": "2021-01-01",
                        "sitelinks": [
                            {
                                "title": "Sitelink Title",
                                "link": "https://example.com/sitelink",
                            }
                        ],
                    }
                ],
                "document_search_results": [
                    {
                        "document": {
                            "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                            "title": "Document Title",
                            "chunks": ["Chunk 1", "Chunk 2"],
                            "metadata": {},
                        },
                    }
                ],
            }
        }


class HybridSearchSettings(R2RSerializable):
    """Settings for hybrid search combining full-text and semantic search."""

    full_text_weight: float = Field(
        default=1.0, description="Weight to apply to full text search"
    )
    semantic_weight: float = Field(
        default=5.0, description="Weight to apply to semantic search"
    )
    full_text_limit: int = Field(
        default=200,
        description="Maximum number of results to return from full text search",
    )
    rrf_k: int = Field(
        default=50, description="K-value for RRF (Rank Reciprocal Fusion)"
    )


class ChunkSearchSettings(R2RSerializable):
    """Settings specific to chunk/vector search."""

    index_measure: IndexMeasure = Field(
        default=IndexMeasure.cosine_distance,
        description="The distance measure to use for indexing",
    )
    probes: int = Field(
        default=10,
        description="Number of ivfflat index lists to query. Higher increases accuracy but decreases speed.",
    )
    ef_search: int = Field(
        default=40,
        description="Size of the dynamic candidate list for HNSW index search. Higher increases accuracy but decreases speed.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether to enable chunk search",
    )


class GraphSearchSettings(R2RSerializable):
    """Settings specific to knowledge graph search."""

    limits: dict[str, int] = Field(
        default={},
    )
    enabled: bool = Field(
        default=True,
        description="Whether to enable graph search",
    )


class SearchSettings(R2RSerializable):
    """Main search settings class that combines shared settings with
    specialized settings for chunks and graph."""

    # Search type flags
    use_hybrid_search: bool = Field(
        default=False,
        description="Whether to perform a hybrid search. This is equivalent to setting `use_semantic_search=True` and `use_fulltext_search=True`, e.g. combining vector and keyword search.",
    )
    use_semantic_search: bool = Field(
        default=True,
        description="Whether to use semantic search",
    )
    use_fulltext_search: bool = Field(
        default=False,
        description="Whether to use full-text search",
    )

    # Common search parameters
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="""Filters to apply to the search. Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.

      Commonly seen filters include operations include the following:

        `{"document_id": {"$eq": "9fbe403b-..."}}`

        `{"document_id": {"$in": ["9fbe403b-...", "3e157b3a-..."]}}`

        `{"collection_ids": {"$overlap": ["122fdf6a-...", "..."]}}`

        `{"$and": {"$document_id": ..., "collection_ids": ...}}`""",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=1_000,
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset to paginate search results",
    )
    include_metadatas: bool = Field(
        default=True,
        description="Whether to include element metadata in the search results",
    )
    include_scores: bool = Field(
        default=True,
        description="""Whether to include search score values in the
        search results""",
    )

    # Search strategy and settings
    search_strategy: str = Field(
        default="vanilla",
        description="""Search strategy to use
        (e.g., 'vanilla', 'query_fusion', 'hyde')""",
    )
    hybrid_settings: HybridSearchSettings = Field(
        default_factory=HybridSearchSettings,
        description="""Settings for hybrid search (only used if
        `use_semantic_search` and `use_fulltext_search` are both true)""",
    )

    # Specialized settings
    chunk_settings: ChunkSearchSettings = Field(
        default_factory=ChunkSearchSettings,
        description="Settings specific to chunk/vector search",
    )
    graph_settings: GraphSearchSettings = Field(
        default_factory=GraphSearchSettings,
        description="Settings specific to knowledge graph search",
    )

    # For HyDE or multi-query:
    num_sub_queries: int = Field(
        default=5,
        description="Number of sub-queries/hypothetical docs to generate when using hyde or rag_fusion search strategies.",
    )

    class Config:
        populate_by_name = True
        json_encoders = {UUID: str}
        json_schema_extra = {
            "example": {
                "use_semantic_search": True,
                "use_fulltext_search": False,
                "use_hybrid_search": False,
                "filters": {"category": "technology"},
                "limit": 20,
                "offset": 0,
                "search_strategy": "vanilla",
                "hybrid_settings": {
                    "full_text_weight": 1.0,
                    "semantic_weight": 5.0,
                    "full_text_limit": 200,
                    "rrf_k": 50,
                },
                "chunk_settings": {
                    "enabled": True,
                    "index_measure": "cosine_distance",
                    "include_metadata": True,
                    "probes": 10,
                    "ef_search": 40,
                },
                "graph_settings": {
                    "enabled": True,
                    "generation_config": GenerationConfig.Config.json_schema_extra,
                    "max_community_description_length": 65536,
                    "max_llm_queries_for_global_search": 250,
                    "limits": {
                        "entity": 20,
                        "relationship": 20,
                        "community": 20,
                    },
                },
            }
        }

    def __init__(self, **data):
        # Handle legacy search_filters field
        data["filters"] = {
            **data.get("filters", {}),
            **data.get("search_filters", {}),
        }
        super().__init__(**data)

    def model_dump(self, *args, **kwargs):
        return super().model_dump(*args, **kwargs)

    @classmethod
    def get_default(cls, mode: str) -> "SearchSettings":
        """Return default search settings for a given mode."""
        if mode == "basic":
            # A simpler search that relies primarily on semantic search.
            return cls(
                use_semantic_search=True,
                use_fulltext_search=False,
                use_hybrid_search=False,
                search_strategy="vanilla",
                # Other relevant defaults can be provided here as needed
            )
        elif mode == "advanced":
            # A more powerful, combined search that leverages both semantic and fulltext.
            return cls(
                use_semantic_search=True,
                use_fulltext_search=True,
                use_hybrid_search=True,
                search_strategy="hyde",
                # Other advanced defaults as needed
            )
        else:
            # For 'custom' or unrecognized modes, return a basic empty config.
            return cls()


class SearchMode(str, Enum):
    """Search modes for the search endpoint."""

    basic = "basic"
    advanced = "advanced"
    custom = "custom"


def select_search_filters(
    auth_user: Any,  # Replace Any with your actual User type hint
    search_settings: SearchSettings,
) -> dict[str, Any]:
    """
    Constructs the final search filters, applying access control for non-superusers.

    - Superusers: Returns the original filters.
    - Non-superusers:
        - If filtering explicitly by 'collection_ids':
            - Restricts results to the intersection of requested and accessible collections.
            - Ownership does NOT bypass this filter.
            - Other filters are ANDed.
        - If NOT filtering explicitly by 'collection_ids':
            - Returns documents owned by the user OR documents in any accessible collection.
            - Other filters are ANDed.
    """
    input_filters = copy(search_settings.filters)

    if auth_user.is_superuser:
        # Superusers bypass access control modifications
        return input_filters

    # Non-superuser logic
    user_collections: Set[UUID] = set(auth_user.collection_ids)
    final_filters: dict[str, Any] = {}
    other_filters: dict[str, Any] = {}
    requested_collections_raw: list | None = None
    collection_filter_key: str | None = None

    # --- Identify if an explicit collection_ids filter exists ---
    # This simple check looks for a top-level key.
    # A more robust implementation might need to parse the filter tree
    # for nested collection_ids filters within $and/$or clauses.
    if "collection_ids" in input_filters and isinstance(
        input_filters["collection_ids"], dict
    ):
        filter_clause = input_filters["collection_ids"]
        if "$overlap" in filter_clause:
            collection_filter_key = "collection_ids"
            requested_collections_raw = filter_clause["$overlap"]
        # Add checks for other potential collection filter operators if needed (e.g., $in)

    # Separate other filters from the identified collection filter
    for key, value in input_filters.items():
        if key != collection_filter_key:
            other_filters[key] = value

    # --- Construct the final filter based on whether collections were specified ---
    if collection_filter_key and requested_collections_raw is not None:
        # Case A: User explicitly filtered by collection_ids

        try:
            # Ensure raw values are strings/UUIDs before converting
            requested_collections = set(
                UUID(str(cid)) for cid in requested_collections_raw
            )
        except (TypeError, ValueError, AttributeError) as e:
            # Handle invalid format gracefully. Options:
            # 1. Raise an error (e.g., HTTPException for API)
            # 2. Log a warning and return empty results for the collection filter
            # 3. Log a warning and ignore the collection filter (fall back to Case B)
            # Choosing option 2: effectively filter for zero allowed collections.
            print(
                f"Warning: Invalid collection_ids format in filter: {e}. Applying empty collection filter."
            )
            allowed_collections = set()
        else:
            # Calculate the intersection of requested and user's accessible collections
            allowed_collections = user_collections.intersection(
                requested_collections
            )

        # The primary access filter is *only* based on these allowed collections
        access_filter = {
            "collection_ids": {"$overlap": list(allowed_collections)}
        }

        # Combine the specific collection access filter with any other filters
        if other_filters:
            final_filters = {"$and": [access_filter, other_filters]}
        else:
            final_filters = access_filter

    else:
        # Case B: User did *not* explicitly filter by collection_ids
        # Apply default visibility: owned OR in *any* accessible collection
        access_filter = {
            "$or": [
                {"owner_id": {"$eq": auth_user.id}},
                # Ensure user_collections is not empty before adding overlap,
                # though overlap with empty list is usually handled ok by DBs.
                {"collection_ids": {"$overlap": list(user_collections)}}
                if user_collections
                else {},
                # Remove empty dict from $or if user_collections is empty
            ]
        }
        # Clean up the $or if one clause is empty
        if not user_collections:
            access_filter = {"owner_id": {"$eq": auth_user.id}}
        elif not auth_user.id:  # Should not happen, but defensive
            access_filter = {
                "collection_ids": {"$overlap": list(user_collections)}
            }

        # Combine the base visibility filter with any other filters provided
        if other_filters:  # Use the separated other_filters
            final_filters = {"$and": [access_filter, other_filters]}
        else:
            final_filters = access_filter  # Use the original input_filters if no collection filter was found

    return final_filters
