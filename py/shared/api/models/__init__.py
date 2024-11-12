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
    UserResponse,
    WrappedTokenResponse,
    WrappedUserResponse,
)
from shared.api.models.ingestion.responses import (
    IngestionResponse,
    WrappedIngestionResponse,
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
    AppSettingsResponse,
    CollectionResponse,
    ConversationResponse,
    DocumentChunkResponse,
    DocumentOverviewResponse,
    LogResponse,
    PromptResponse,
    ScoreCompletionResponse,
    ServerStats,
    UserOverviewResponse,
    WrappedAddUserResponse,
    WrappedAnalyticsResponse,
    WrappedAppSettingsResponse,
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedDocumentChunkResponse,
    WrappedDocumentChunksResponse,
    WrappedDocumentOverviewResponse,
    WrappedDocumentResponse,
    # Prompt Responses
    WrappedPromptResponse,
    WrappedPromptsResponse,
    # Collection Responses
    WrappedUserOverviewResponse,
    WrappedUsersOverviewResponse,
    WrappedLogResponse,
    WrappedPromptMessageResponse,
    WrappedServerStatsResponse,
    WrappedUserCollectionResponse,
    WrappedUsersInCollectionResponse,
)
from shared.api.models.retrieval.responses import (
    CombinedSearchResponse,
    RAGAgentResponse,
    RAGResponse,
    WrappedRAGAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
    WrappedVectorSearchResponse,
)

__all__ = [
    # Auth Responses
    "GenericMessageResponse",
    "TokenResponse",
    "UserResponse",
    "WrappedTokenResponse",
    "WrappedUserResponse",
    "WrappedGenericMessageResponse",
    # Ingestion Responses
    "IngestionResponse",
    "WrappedIngestionResponse",
    "WrappedUpdateResponse",
    # Restructure Responses
    "KGCreationResponse",
    "WrappedKGCreationResponse",
    "KGEnrichmentResponse",
    "WrappedKGEnrichmentResponse",
    # Management Responses
    "PromptResponse",
    "ServerStats",
    "LogResponse",
    "AnalyticsResponse",
    "AppSettingsResponse",
    "ScoreCompletionResponse",
    "UserOverviewResponse",
    "DocumentOverviewResponse",
    "DocumentChunkResponse",
    "CollectionResponse",
    "ConversationResponse",
    "WrappedPromptMessageResponse",
    "WrappedServerStatsResponse",
    "WrappedLogResponse",
    "WrappedAnalyticsResponse",
    "WrappedAppSettingsResponse",
    "WrappedConversationResponse",
    "WrappedDocumentOverviewResponse",
    "WrappedDocumentResponse",
    # Collection Responses
    "WrappedCollectionResponse",
    "WrappedCollectionsResponse",
    "WrappedAddUserResponse",
    "WrappedUsersInCollectionResponse",
    # Prompt Responses
    "WrappedPromptResponse",
    "WrappedPromptsResponse",
    # Chunk Responses
    "WrappedDocumentChunkResponse",
    "WrappedDocumentChunksResponse",
    # Conversation Responses
    "WrappedUserOverviewResponse",
    "WrappedUsersOverviewResponse",
    # Base Responses
    "PaginatedResultsWrapper",
    "ResultsWrapper",
    "GenericBooleanResponse",
    "GenericMessageResponse",
    "WrappedBooleanResponse",
    "WrappedGenericMessageResponse",
    # TODO: Clean up the following responses
    "WrappedUserCollectionResponse",
    "WrappedConversationsResponse",
    # Retrieval Responses
    "CombinedSearchResponse",
    "RAGResponse",
    "RAGAgentResponse",
    "WrappedSearchResponse",
    "WrappedVectorSearchResponse",
    "WrappedRAGResponse",
    "WrappedRAGAgentResponse",
]
