from enum import Enum
from typing import Optional

from shared.abstractions import (  # ChunkingConfig,
    GenerationConfig,
    HybridSearchSettings,
    KGCommunityResult,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityResult,
    KGGlobalResult,
    KGRelationshipResult,
    KGSearchMethod,
    KGSearchResult,
    KGSearchResultType,
    KGSearchSettings,
    Message,
    MessageType,
    R2RException,
    R2RSerializable,
    Token,
    VectorSearchResult,
    VectorSearchSettings,
)
from shared.api.models import (
    KGCreationResponse,
    KGEnrichmentResponse,
    RAGResponse,
    SearchResponse,
    UserResponse,
)


class Strategy(str, Enum):
    # Unstructured methods
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
