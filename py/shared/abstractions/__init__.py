from shared.shared_abstractions.completion import CompletionRecord, MessageType
from shared.shared_abstractions.document import (
    DataType,
    Document,
    DocumentExtraction,
    DocumentFragment,
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    RestructureStatus,
)
from shared.shared_abstractions.embedding import (
    EmbeddingPurpose,
    default_embedding_prefixes,
)
from shared.shared_abstractions.exception import (
    R2RDocumentProcessingError,
    R2RException,
)
from shared.shared_abstractions.graph import (
    Community,
    CommunityReport,
    Entity,
    EntityType,
    KGExtraction,
    RelationshipType,
    Triple,
)
from shared.shared_abstractions.llm import (
    GenerationConfig,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    Message,
    RAGCompletion,
)
from shared.shared_abstractions.prompt import Prompt
from shared.shared_abstractions.restructure import (
    KGCreationSettings,
    KGEnrichmentSettings,
)
from shared.shared_abstractions.search import (
    AggregateSearchResult,
    HybridSearchSettings,
    KGCommunityResult,
    KGEntityResult,
    KGGlobalResult,
    KGRelationshipResult,
    KGSearchMethod,
    KGSearchResult,
    KGSearchResultType,
    KGSearchSettings,
    VectorSearchResult,
    VectorSearchSettings,
)
from shared.shared_abstractions.shared_base import (
    AsyncSyncMeta,
    R2RSerializable,
    syncable,
)
from shared.shared_abstractions.user import Token, TokenData, UserStats
from shared.shared_abstractions.vector import (
    StorageResult,
    Vector,
    VectorEntry,
    VectorType,
)

__all__ = [
    # Base abstractions
    "R2RSerializable",
    "AsyncSyncMeta",
    "syncable",
    # Completion abstractions
    "CompletionRecord",
    "MessageType",
    # Document abstractions
    "DataType",
    "Document",
    "DocumentExtraction",
    "DocumentFragment",
    "DocumentInfo",
    "IngestionStatus",
    "RestructureStatus",
    "DocumentType",
    # Embedding abstractions
    "EmbeddingPurpose",
    "default_embedding_prefixes",
    # Exception abstractions
    "R2RDocumentProcessingError",
    "R2RException",
    # Graph abstractions
    "Entity",
    "EntityType",
    "RelationshipType",
    "Community",
    "CommunityReport",
    "KGExtraction",
    "Triple",
    # LLM abstractions
    "GenerationConfig",
    "LLMChatCompletion",
    "LLMChatCompletionChunk",
    "Message",
    "RAGCompletion",
    # Prompt abstractions
    "Prompt",
    # Search abstractions
    "AggregateSearchResult",
    "KGSearchResult",
    "KGSearchMethod",
    "KGSearchResultType",
    "KGEntityResult",
    "KGRelationshipResult",
    "KGCommunityResult",
    "KGGlobalResult",
    "KGSearchSettings",
    "VectorSearchResult",
    "VectorSearchSettings",
    "HybridSearchSettings",
    # Restructure abstractions
    "KGCreationSettings",
    "KGEnrichmentSettings",
    # User abstractions
    "Token",
    "TokenData",
    "UserStats",
    # Vector abstractions
    "Vector",
    "VectorEntry",
    "VectorType",
    "StorageResult",
]
