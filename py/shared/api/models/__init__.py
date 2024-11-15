from shared.api.models.base import (
    PaginatedResultsWrapper,
    ResultsWrapper,
    GenericBooleanResponse,
    GenericMessageResponse,
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
)
from shared.api.models.auth.responses import (
    TokenResponse,
    WrappedTokenResponse,
)
from shared.api.models.ingestion.responses import (
    IngestionResponse,
    WrappedIngestionResponse,
    WrappedMetadataUpdateResponse,
    WrappedUpdateResponse,
)
from shared.api.models.kg.responses import (
    KGCreationResponse,
    KGEnrichmentResponse,
    KGEntityDeduplicationResponse,
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntityDeduplicationResponse,
)
from shared.api.models.management.responses import (
    AnalyticsResponse,
    ChunkResponse,
    CollectionResponse,
    ConversationResponse,
    LogResponse,
    PromptResponse,
    ServerStats,
    SettingsResponse,
    UserResponse,
    # Chunk Responses
    WrappedChunkResponse,
    WrappedChunksResponse,
    # Conversation Responses
    WrappedConversationResponse,
    WrappedConversationsResponse,
    # Document Responses
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
    # Collection Responses
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    # Prompt Responses
    WrappedPromptResponse,
    WrappedPromptsResponse,
    # System Responses
    WrappedAnalyticsResponse,
    WrappedSettingsResponse,
    # User Responses
    WrappedUserResponse,
    WrappedUsersResponse,
    WrappedLogResponse,
    WrappedServerStatsResponse,
)
from shared.api.models.retrieval.responses import (
    CombinedSearchResponse,
    AgentResponse,
    RAGResponse,
    WrappedDocumentSearchResponse,
    WrappedAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
    WrappedVectorSearchResponse,
)

__all__ = [
    # Auth Responses
    "GenericMessageResponse",
    "TokenResponse",
    "WrappedTokenResponse",
    "WrappedGenericMessageResponse",
    # Ingestion Responses
    "IngestionResponse",
    "WrappedIngestionResponse",
    "WrappedUpdateResponse",
    "WrappedMetadataUpdateResponse",
    # Restructure Responses
    "KGCreationResponse",
    "KGEnrichmentResponse",
    "KGEntityDeduplicationResponse",
    "WrappedKGCreationResponse",
    "WrappedKGEnrichmentResponse",
    "WrappedKGEntityDeduplicationResponse",
    # Management Responses
    "PromptResponse",
    "ServerStats",
    "LogResponse",
    "AnalyticsResponse",
    "SettingsResponse",
    "ChunkResponse",
    "CollectionResponse",
    "ConversationResponse",
    "WrappedServerStatsResponse",
    "WrappedLogResponse",
    "WrappedAnalyticsResponse",
    "WrappedSettingsResponse",
    # Document Responses
    "WrappedDocumentResponse",
    "WrappedDocumentsResponse",
    # Collection Responses
    "WrappedCollectionResponse",
    "WrappedCollectionsResponse",
    # Prompt Responses
    "WrappedPromptResponse",
    "WrappedPromptsResponse",
    # Chunk Responses
    "WrappedChunkResponse",
    "WrappedChunksResponse",
    # Conversation Responses
    "WrappedConversationResponse",
    "WrappedConversationsResponse",
    # User Responses
    "UserResponse",
    "WrappedUserResponse",
    "WrappedUsersResponse",
    # Base Responses
    "PaginatedResultsWrapper",
    "ResultsWrapper",
    "GenericBooleanResponse",
    "GenericMessageResponse",
    "WrappedBooleanResponse",
    "WrappedGenericMessageResponse",
    # TODO: Clean up the following responses
    # Retrieval Responses
    "CombinedSearchResponse",
    "RAGResponse",
    "WrappedRAGResponse",
    "AgentResponse",
    "WrappedSearchResponse",
    "WrappedDocumentSearchResponse",
    "WrappedVectorSearchResponse",
    "WrappedAgentResponse",
]
