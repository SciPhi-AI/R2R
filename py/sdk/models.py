from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, Optional, Type, Union
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationConfig(BaseModel):
    _defaults: ClassVar[dict] = {
        "model": "openai/gpt-4o",
        "temperature": 0.1,
        "top_p": 1.0,
        "max_tokens_to_sample": 1024,
        "stream": False,
        "functions": None,
        "tools": None,
        "add_generation_kwargs": None,
        "api_base": None,
    }

    model: str = Field(
        default_factory=lambda: GenerationConfig._defaults["model"]
    )
    temperature: float = Field(
        default_factory=lambda: GenerationConfig._defaults["temperature"]
    )
    top_p: float = Field(
        default_factory=lambda: GenerationConfig._defaults["top_p"]
    )
    max_tokens_to_sample: int = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "max_tokens_to_sample"
        ]
    )
    stream: bool = Field(
        default_factory=lambda: GenerationConfig._defaults["stream"]
    )
    functions: Optional[list[dict]] = Field(
        default_factory=lambda: GenerationConfig._defaults["functions"]
    )
    tools: Optional[list[dict]] = Field(
        default_factory=lambda: GenerationConfig._defaults["tools"]
    )
    add_generation_kwargs: Optional[dict] = Field(
        default_factory=lambda: GenerationConfig._defaults[
            "add_generation_kwargs"
        ]
    )
    api_base: Optional[str] = Field(
        default_factory=lambda: GenerationConfig._defaults["api_base"]
    )

    @classmethod
    def set_default(cls, **kwargs):
        for key, value in kwargs.items():
            if key in cls._defaults:
                cls._defaults[key] = value
            else:
                raise AttributeError(
                    f"No default attribute '{key}' in GenerationConfig"
                )

    def __init__(self, **data):
        model = data.pop("model", None)
        if model is not None:
            super().__init__(model=model, **data)
        else:
            super().__init__(**data)


class KGSearchSettings(BaseModel):
    use_kg_search: bool = False
    kg_search_type: str = "global"  # 'global' or 'local'
    kg_search_level: Optional[str] = None
    kg_search_generation_config: Optional[GenerationConfig] = Field(
        default_factory=GenerationConfig
    )
    entity_types: list = []
    relationships: list = []
    max_community_description_length: int = 4096 * 4
    max_llm_queries_for_global_search: int = 250
    local_search_limits: dict[str, int] = {
        "__Entity__": 20,
        "__Relationship__": 20,
        "__Community__": 20,
    }


class ProviderConfig(BaseModel, ABC):
    """A base provider configuration class"""

    extra_fields: dict[str, Any] = {}
    provider: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        ignore_extra = True

    @abstractmethod
    def validate(self) -> None:
        pass

    @classmethod
    def create(cls: Type["ProviderConfig"], **kwargs: Any) -> "ProviderConfig":
        base_args = cls.model_fields.keys()
        filtered_kwargs = {
            k: v if v != "None" else None
            for k, v in kwargs.items()
            if k in base_args
        }
        instance = cls(**filtered_kwargs)
        for k, v in kwargs.items():
            if k not in base_args:
                instance.extra_fields[k] = v
        return instance

    @property
    @abstractmethod
    def supported_providers(self) -> list[str]:
        """Define a list of supported providers."""
        pass


class MessageType(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"

    def __str__(self):
        return self.value


class Message(BaseModel):
    role: Union[MessageType, str]
    content: Optional[str] = None
    name: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[list[Dict[str, Any]]] = None


class Method(str, Enum):
    BY_TITLE = "by_title"
    BASIC = "basic"
    RECURSIVE = "recursive"
    CHARACTER = "character"


class ChunkingConfig(ProviderConfig):
    provider: str = "r2r"
    method: Method = Method.RECURSIVE
    chunk_size: int = 512
    chunk_overlap: int = 20
    max_chunk_size: Optional[int] = None

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured", None]

    class Config:
        json_schema_extra = {
            "type": "object",
            "properties": {
                "provider": {"type": "string"},
                "method": {"type": "string"},
                "chunk_size": {"type": "integer"},
                "chunk_overlap": {"type": "integer"},
                "max_chunk_size": {"type": "integer"},
            },
            "required": ["provider", "method", "chunk_size", "chunk_overlap"],
            "example": {
                "provider": "r2r",
                "method": "recursive",
                "chunk_size": 512,
                "chunk_overlap": 20,
                "max_chunk_size": 1024,
            },
        }


class KGLocalSearchResult(BaseModel):
    query: str
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    communities: list[dict[str, Any]]

    def __str__(self) -> str:
        return f"KGLocalSearchResult(query={self.query}, entities={self.entities}, relationships={self.relationships}, communities={self.communities})"

    def dict(self) -> dict:
        return {
            "query": self.query,
            "entities": self.entities,
            "relationships": self.relationships,
            "communities": self.communities,
        }


class KGGlobalSearchResult(BaseModel):
    query: str
    search_result: list[str]

    def __str__(self) -> str:
        return f"KGGlobalSearchResult(query={self.query}, search_result={self.search_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {"query": self.query, "search_result": self.search_result}


class KGSearchResult(BaseModel):
    local_result: Optional[KGLocalSearchResult] = None
    global_result: Optional[KGGlobalSearchResult] = None

    def __str__(self) -> str:
        return f"KGSearchResult(local_result={self.local_result}, global_result={self.global_result})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "local_result": (
                self.local_result.dict() if self.local_result else None
            ),
            "global_result": (
                self.global_result.dict() if self.global_result else None
            ),
        }

    class Config:
        json_schema_extra = {
            "example": {
                "local_result": {
                    "query": "What is the capital of France?",
                    "entities": {
                        "Paris": {
                            "name": "Paris",
                            "description": "Paris is the capital of France.",
                        }
                    },
                    "relationships": {},
                    "communities": {},
                },
                "global_result": {
                    "query": "What is the capital of France?",
                    "search_result": [
                        "Paris is the capital and most populous city of France."
                    ],
                },
            }
        }


class R2RException(Exception):
    def __init__(
        self, message: str, status_code: int, detail: Optional[Any] = None
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class Token(BaseModel):
    token: str
    token_type: str


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


class HybridSearchSettings(BaseModel):
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


class VectorSearchSettings(BaseModel):
    use_vector_search: bool = Field(
        default=True, description="Whether to use vector search"
    )
    use_hybrid_search: bool = Field(
        default=False,
        description="Whether to perform a hybrid search (combining vector and keyword search)",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the vector search",
    )
    search_limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=1_000,
    )
    selected_group_ids: list[UUID] = Field(
        default_factory=list,
        description="Group IDs to search for",
    )
    index_measure: IndexMeasure = Field(
        default=IndexMeasure.cosine_distance,
        description="The distance measure to use for indexing",
    )
    include_values: bool = Field(
        default=True,
        description="Whether to include search score values in the search results",
    )
    include_metadatas: bool = Field(
        default=True,
        description="Whether to include element metadata in the search results",
    )
    probes: Optional[int] = Field(
        default=10,
        description="Number of ivfflat index lists to query. Higher increases accuracy but decreases speed.",
    )
    ef_search: Optional[int] = Field(
        default=40,
        description="Size of the dynamic candidate list for HNSW index search. Higher increases accuracy but decreases speed.",
    )
    hybrid_search_settings: Optional[HybridSearchSettings] = Field(
        default=HybridSearchSettings(),
        description="Settings for hybrid search",
    )

    class Config:
        json_encoders = {UUID: str}
        json_schema_extra = {
            "use_vector_search": True,
            "use_hybrid_search": True,
            "filters": {"category": "technology"},
            "search_limit": 20,
            "selected_group_ids": [
                "2acb499e-8428-543b-bd85-0d9098718220",
                "3e157b3a-8469-51db-90d9-52e7d896b49b",
            ],
            "index_measure": "cosine_distance",
            "include_metadata": True,
            "probes": 10,
            "ef_search": 40,
            "hybrid_search_settings": {
                "full_text_weight": 1.0,
                "semantic_weight": 5.0,
                "full_text_limit": 200,
                "rrf_k": 50,
            },
        }

    def model_dump(self, *args, **kwargs):
        dump = super().model_dump(*args, **kwargs)
        dump["selected_group_ids"] = [
            str(uuid) for uuid in dump["selected_group_ids"]
        ]
        return dump


class KGEnrichmentSettings(BaseModel):
    max_knowledge_triples: int = Field(
        default=100,
        description="The maximum number of knowledge triples to extract from each chunk.",
    )
    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="The generation configuration for the KG enrichment.",
    )
    leiden_params: dict = Field(
        default_factory=dict,
        description="The parameters for the Leiden algorithm.",
    )


class KGEnrichmentResponse(BaseModel):
    enriched_content: Dict[str, Any]


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_verified: bool = False
    group_ids: list[UUID] = []

    # Optional fields (to update or set at creation)
    hashed_password: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


class VectorSearchResult(BaseModel):
    """Result of a search operation."""

    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    group_ids: list[UUID]
    score: float
    text: str
    metadata: dict[str, Any]

    def __str__(self) -> str:
        return f"VectorSearchResult(fragment_id={self.fragment_id}, extraction_id={self.extraction_id}, document_id={self.document_id}, score={self.score})"

    def __repr__(self) -> str:
        return self.__str__()

    def dict(self) -> dict:
        return {
            "fragment_id": self.fragment_id,
            "extraction_id": self.extraction_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "group_ids": self.group_ids,
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
        }

    class Config:
        json_schema_extra = {
            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
            "group_ids": [],
            "score": 0.23943702876567796,
            "text": "Example text from the document",
            "metadata": {
                "title": "example_document.pdf",
                "associatedQuery": "What is the capital of France?",
            },
        }


class SearchResponse(BaseModel):
    vector_search_results: list[VectorSearchResult] = Field(
        ...,
        description="List of vector search results",
    )
    kg_search_results: Optional[list[KGSearchResult]] = Field(
        None,
        description="Knowledge graph search results, if applicable",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "vector_search_results": [
                    {
                        "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                        "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                        "group_ids": [],
                        "score": 0.23943702876567796,
                        "text": "Example text from the document",
                        "metadata": {
                            "title": "example_document.pdf",
                            "associatedQuery": "What is the capital of France?",
                        },
                    }
                ],
                "kg_search_results": None,
            }
        }


class RAGResponse(BaseModel):
    completion: Any = Field(
        ...,
        description="The generated completion from the RAG process",
    )
    search_results: SearchResponse = Field(
        ...,
        description="The search results used for the RAG process",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "completion": {
                    "id": "chatcmpl-example123",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "logprobs": None,
                            "message": {
                                "content": "Paris is the capital of France.",
                                "role": "assistant",
                            },
                        }
                    ],
                },
                "search_results": {
                    "vector_search_results": [
                        {
                            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                            "group_ids": [],
                            "score": 0.23943702876567796,
                            "text": "Paris is the capital and most populous city of France.",
                            "metadata": {
                                "text": "Paris is the capital and most populous city of France.",
                                "title": "france_info.pdf",
                                "associatedQuery": "What is the capital of France?",
                            },
                        }
                    ],
                    "kg_search_results": None,
                },
            }
        }
