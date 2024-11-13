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
    AppSettingsResponse,
    CollectionResponse,
    ConversationResponse,
    DocumentChunkResponse,
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
    # Document Responses
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
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
    WrappedDocumentSearchResponse,
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
    "WrappedMetadataUpdateResponse",
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
    "DocumentChunkResponse",
    "CollectionResponse",
    "ConversationResponse",
    "WrappedPromptMessageResponse",
    "WrappedServerStatsResponse",
    "WrappedLogResponse",
    "WrappedAnalyticsResponse",
    "WrappedAppSettingsResponse",
    "WrappedConversationResponse",
    # Document Responses
    "WrappedDocumentResponse",
    "WrappedDocumentsResponse",
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
    "WrappedDocumentSearchResponse",
    "WrappedVectorSearchResponse",
    "WrappedRAGResponse",
    "WrappedRAGAgentResponse",
]
