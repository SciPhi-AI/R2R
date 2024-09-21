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
