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
    UpdateResponse,
    WrappedIngestionResponse,
    WrappedListVectorIndicesResponse,
    WrappedMetadataUpdateResponse,
    WrappedUpdateResponse,
)
from shared.api.models.kg.responses import (
    KGCreationEstimationResponse,
    KGCreationResponse,
    KGDeduplicationEstimationResponse,
    KGEnrichmentEstimationResponse,
    KGEnrichmentResponse,
    KGEntityDeduplicationResponse,
    WrappedKGCommunitiesResponse,
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntitiesResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGTriplesResponse,
    WrappedKGTunePromptResponse,
)
from shared.api.models.management.responses import (
    AnalyticsResponse,
    AppSettingsResponse,
    CollectionResponse,
    ConversationResponse,
    ChunkResponse,
    UserResponse,
    LogResponse,
    PromptResponse,
    ServerStats,
    WrappedAnalyticsResponse,
    WrappedAppSettingsResponse,
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    # Document Responses
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
    # Prompt Responses
    WrappedPromptResponse,
    WrappedPromptsResponse,
    WrappedLogResponse,
    # Chunk Responses
    WrappedChunkResponse,
    WrappedChunksResponse,
    # Conversation Responses
    WrappedMessageResponse,
    WrappedMessagesResponse,
    WrappedBranchResponse,
    WrappedBranchesResponse,
    # User Responses
    WrappedUserResponse,
    WrappedUsersResponse,
    # TODO: anything below this hasn't been reviewed
    WrappedServerStatsResponse,
    WrappedVerificationResult,
)
from shared.api.models.retrieval.responses import (
    CombinedSearchResponse,
    RAGAgentResponse,
    RAGResponse,
    WrappedCompletionResponse,
    WrappedDocumentSearchResponse,
    WrappedRAGAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
    WrappedVectorSearchResponse,
)

__all__ = [
    # Auth Responses
    "TokenResponse",
    "WrappedTokenResponse",
    "WrappedVerificationResult",
    "WrappedGenericMessageResponse",
    # Ingestion Responses
    "IngestionResponse",
    "WrappedIngestionResponse",
    "WrappedUpdateResponse",
    "WrappedMetadataUpdateResponse",
    "WrappedListVectorIndicesResponse",
    "UpdateResponse",
    # Knowledge Graph Responses
    "KGCreationResponse",
    "WrappedKGCreationResponse",
    "KGEnrichmentResponse",
    "WrappedKGEnrichmentResponse",
    "KGEntityDeduplicationResponse",
    "WrappedKGEntityDeduplicationResponse",
    "WrappedKGTunePromptResponse",
    "KGCreationEstimationResponse",
    "KGDeduplicationEstimationResponse",
    "KGEnrichmentEstimationResponse",
    # Management Responses
    "PromptResponse",
    "ServerStats",
    "LogResponse",
    "AnalyticsResponse",
    "AppSettingsResponse",
    "ChunkResponse",
    "CollectionResponse",
    "WrappedServerStatsResponse",
    "WrappedLogResponse",
    "WrappedAnalyticsResponse",
    "WrappedAppSettingsResponse",
    "WrappedDocumentResponse",
    "WrappedDocumentsResponse",
    "WrappedCollectionResponse",
    "WrappedCollectionsResponse",
    # Conversation Responses
    "ConversationResponse",
    "WrappedConversationResponse",
    "WrappedConversationsResponse",
    # Prompt Responses
    "WrappedPromptResponse",
    "WrappedPromptsResponse",
    # Conversation Responses
    "WrappedMessageResponse",
    "WrappedMessagesResponse",
    "WrappedBranchResponse",
    "WrappedBranchesResponse",
    # Chunk Responses
    "WrappedChunkResponse",
    "WrappedChunksResponse",
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
    # TODO: This needs to be cleaned up
    # Retrieval Responses
    "CombinedSearchResponse",
    "RAGResponse",
    "RAGAgentResponse",
    "WrappedDocumentSearchResponse",
    "WrappedSearchResponse",
    "WrappedVectorSearchResponse",
    "WrappedCompletionResponse",
    "WrappedRAGResponse",
    "WrappedRAGAgentResponse",
]
