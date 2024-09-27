from enum import Enum
from typing import Optional

from shared.abstractions import (
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
