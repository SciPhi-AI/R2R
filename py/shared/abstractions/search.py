"""Abstractions for search functionality."""

from copy import copy
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig
from .vector import IndexMeasure


class ChunkSearchResult(R2RSerializable):
    """Result of a search operation."""

    id: UUID
    document_id: UUID
    owner_id: Optional[UUID]
    collection_ids: list[UUID]
    score: float
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"ChunkSearchResult(id={self.id}, document_id={self.document_id}, score={self.score})"

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


class KGSearchResultType(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    COMMUNITY = "community"


class KGEntityResult(R2RSerializable):
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Entity Name",
            "description": "Entity Description",
            "metadata": {},
        }


class KGRelationshipResult(R2RSerializable):
    # name: str
    subject: str
    predicate: str
    object: str
    metadata: Optional[dict[str, Any]] = None
    score: Optional[float] = None
    # name: str
    # description: str
    # metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Relationship Name",
            "description": "Relationship Description",
            "metadata": {},
        }


class KGCommunityResult(R2RSerializable):
    name: str
    summary: str
    rating: float
    rating_explanation: str
    findings: list[str]
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Community Name",
            "summary": "Community Summary",
            "rating": 9,
            "rating_explanation": "Rating Explanation",
            "findings": ["Finding 1", "Finding 2"],
            "metadata": {},
        }


class KGGlobalResult(R2RSerializable):
    name: str
    description: str
    metadata: Optional[dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "name": "Global Result Name",
            "description": "Global Result Description",
            "metadata": {},
        }


class GraphSearchResult(R2RSerializable):
    content: (
        KGEntityResult
        | KGRelationshipResult
        | KGCommunityResult
        | KGGlobalResult
    )
    result_type: Optional[KGSearchResultType] = None
    chunk_ids: Optional[list[UUID]] = None
    metadata: dict[str, Any] = {}
    score: Optional[float] = None

    class Config:
        json_schema_extra = {
            "content": KGEntityResult.Config.json_schema_extra,
            "result_type": "entity",
            "chunk_ids": ["c68dc72e-fc23-5452-8f49-d7bd46088a96"],
            "metadata": {"associated_query": "What is the capital of France?"},
        }


class WebSearchResult(R2RSerializable):
    title: str
    link: str
    snippet: str
    position: int
    type: str = "organic"
    date: Optional[str] = None
    sitelinks: Optional[list[dict]] = None


class RelatedSearchResult(R2RSerializable):
    query: str
    type: str = "related"


class PeopleAlsoAskResult(R2RSerializable):
    question: str
    snippet: str
    link: str
    title: str
    type: str = "peopleAlsoAsk"


class WebSearchResponse(R2RSerializable):
    organic_results: list[WebSearchResult] = []
    related_searches: list[RelatedSearchResult] = []
    people_also_ask: list[PeopleAlsoAskResult] = []

    @classmethod
    def from_serper_results(cls, results: list[dict]) -> "WebSearchResponse":
        organic = []
        related = []
        paa = []

        for result in results:
            if result["type"] == "organic":
                organic.append(WebSearchResult(**result))
            elif result["type"] == "relatedSearches":
                related.append(RelatedSearchResult(**result))
            elif result["type"] == "peopleAlsoAsk":
                paa.append(PeopleAlsoAskResult(**result))

        return cls(
            organic_results=organic,
            related_searches=related,
            people_also_ask=paa,
        )


class AggregateSearchResult(R2RSerializable):
    """Result of an aggregate search operation."""

    chunk_search_results: Optional[list[ChunkSearchResult]]
    graph_search_results: Optional[list[GraphSearchResult]] = None
    web_search_results: Optional[list[WebSearchResult]] = None

    def __str__(self) -> str:
        return f"AggregateSearchResult(chunk_search_results={self.chunk_search_results}, graph_search_results={self.graph_search_results}, web_search_results={self.web_search_results})"

    def __repr__(self) -> str:
        return f"AggregateSearchResult(chunk_search_results={self.chunk_search_results}, graph_search_results={self.graph_search_results}, web_search_results={self.web_search_results})"

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
        }


from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig
from .vector import IndexMeasure


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

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph search.",
    )
    graphrag_map_system: str = Field(
        default="graphrag_map_system",
        description="The system prompt for the graphrag map prompt.",
    )
    graphrag_reduce_system: str = Field(
        default="graphrag_reduce_system",
        description="The system prompt for the graphrag reduce prompt.",
    )
    max_community_description_length: int = Field(
        default=65536,
    )
    max_llm_queries_for_global_search: int = Field(
        default=250,
    )
    limits: dict[str, int] = Field(
        default={},
    )
    enabled: bool = Field(
        default=True,
        description="Whether to enable graph search",
    )


class SearchSettings(R2RSerializable):
    """Main search settings class that combines shared settings with specialized settings for chunks and KG."""

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
        description="Whether to include search score values in the search results",
    )

    # Search strategy and settings
    search_strategy: str = Field(
        default="vanilla",
        description="Search strategy to use (e.g., 'vanilla', 'query_fusion', 'hyde')",
    )
    hybrid_settings: HybridSearchSettings = Field(
        default_factory=HybridSearchSettings,
        description="Settings for hybrid search (only used if `use_semantic_search` and `use_fulltext_search` are both true)",
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

    class Config:
        populate_by_name = True
        json_encoders = {UUID: str}
        json_schema_extra = {
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

    def __init__(self, **data):
        # Handle legacy search_filters field
        data["filters"] = {
            **data.get("filters", {}),
            **data.get("search_filters", {}),
        }
        super().__init__(**data)

    def model_dump(self, *args, **kwargs):
        dump = super().model_dump(*args, **kwargs)
        return dump

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
    auth_user: Any,
    search_settings: SearchSettings,
) -> dict[str, Any]:

    filters = copy(search_settings.filters)
    selected_collections = None
    if not auth_user.is_superuser:
        user_collections = set(auth_user.collection_ids)
        for key in filters.keys():
            if "collection_ids" in key:
                selected_collections = set(filters[key]["$overlap"])
                break

        if selected_collections:
            allowed_collections = user_collections.intersection(
                selected_collections
            )
        else:
            allowed_collections = user_collections
        # for non-superusers, we filter by user_id and selected & allowed collections
        collection_filters = {
            "$or": [
                {"owner_id": {"$eq": auth_user.id}},
                {"collection_ids": {"$overlap": list(allowed_collections)}},
            ]  # type: ignore
        }

        filters.pop("collection_ids", None)

        filters = {"$and": [collection_filters, filters]}  # type: ignore

    return filters
