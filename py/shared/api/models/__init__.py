from shared.api.models.auth.responses import (
    TokenResponse,
    WrappedTokenResponse,
)
from shared.api.models.base import (
    GenericBooleanResponse,
    GenericMessageResponse,
    PaginatedResultsWrapper,
    ResultsWrapper,
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
)
from shared.api.models.ingestion.responses import (
    IngestionResponse,
    WrappedIngestionResponse,
    WrappedMetadataUpdateResponse,
    WrappedUpdateResponse,
)
from shared.api.models.kg.responses import (  # TODO: Need to review anything above this
    GraphResponse,
    KGEnrichmentResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedKGEnrichmentResponse,
)
from shared.api.models.management.responses import (  # Chunk Responses; Conversation Responses; Document Responses; Collection Responses; Prompt Responses; System Responses; User Responses
    AnalyticsResponse,
    ChunkResponse,
    CollectionResponse,
    ConversationResponse,
    LogResponse,
    PromptResponse,
    ServerStats,
    SettingsResponse,
    UserResponse,
    WrappedAnalyticsResponse,
    WrappedChunkResponse,
    WrappedChunksResponse,
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedConversationMessagesResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
    WrappedLogsResponse,
    WrappedPromptResponse,
    WrappedPromptsResponse,
    WrappedServerStatsResponse,
    WrappedSettingsResponse,
    WrappedUserResponse,
    WrappedUsersResponse,
)
from shared.api.models.retrieval.responses import (
    AgentResponse,
    CombinedSearchResponse,
    RAGResponse,
    WrappedAgentResponse,
    WrappedDocumentSearchResponse,
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
    "KGEnrichmentResponse",
    "WrappedKGEnrichmentResponse",
    # TODO: Need to review anything above this
    "GraphResponse",
    "WrappedGraphResponse",
    "WrappedGraphsResponse",
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
    "WrappedLogsResponse",
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
    "WrappedConversationMessagesResponse",
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
