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
    max_community_description_length: int = 65536
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
    # R2R methods
    RECURSIVE = "recursive"
    CHARACTER = "character"


# TODO - Remove this class
class ChunkingConfig(R2RSerializable):
    provider: str = "unstructured_local"  # or unstructured_api

    combine_under_n_chars: Optional[int] = 128
    max_characters: Optional[int] = 500
    coordinates: bool = False
    encoding: Optional[str] = "utf-8"
    extract_image_block_types: Optional[list[str]] = None
    gz_uncompressed_content_type: Optional[str] = None
    hi_res_model_name: Optional[str] = None
    include_orig_elements: Optional[bool] = True
    include_page_breaks: bool = False

    languages: Optional[list[str]] = None
    multipage_sections: bool = True
    new_after_n_chars: Optional[int] = 1500
    ocr_languages: Optional[list[str]] = None
    output_format: str = "application/json"
    overlap: int = 0
    overlap_all: bool = False
    pdf_infer_table_structure: bool = True

    similarity_threshold: Optional[float] = None
    skip_infer_table_types: Optional[list[str]] = None
    split_pdf_concurrency_level: int = 5
    split_pdf_page: bool = True
    starting_page_number: Optional[int] = None
    strategy: str = "auto"
    chunking_strategy: Strategy = Strategy.BY_TITLE
    unique_element_ids: bool = False
    xml_keep_tags: bool = False

    def validate_config(self) -> None:
        if self.strategy not in ["auto", "fast", "hi_res"]:
            raise ValueError("strategy must be 'auto', 'fast', or 'hi_res'")


__all__ = [
    "GenerationConfig",
    "KGSearchSettings",
    "MessageType",
    "Message",
    "ChunkingConfig",
    "KGSearchResultType",
    "KGSearchMethod",
    "KGEntityResult",
    "KGRelationshipResult",
    "KGCommunityResult",
    "KGGlobalResult",
    "KGSearchResult",
    "R2RException",
    "Token",
    "HybridSearchSettings",
    "VectorSearchSettings",
    "KGCreationSettings",
    "KGEnrichmentSettings",
    "KGCreationResponse",
    "KGEnrichmentResponse",
    "UserResponse",
    "VectorSearchResult",
    "SearchResponse",
    "RAGResponse",
]
