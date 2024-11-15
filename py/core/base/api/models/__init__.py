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
    KGCreationResponse,
    KGEnrichmentResponse,
    KGEntityDeduplicationResponse,
    WrappedKGCommunitiesResponse,
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntitiesResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGRelationshipsResponse,
    WrappedKGTunePromptResponse,
)


from shared.api.models.kg.responses_v3 import (
    WrappedKGEntitiesResponse as WrappedKGEntitiesResponseV3,
    WrappedKGRelationshipsResponse as WrappedKGRelationshipsResponseV3,
    WrappedKGCommunitiesResponse as WrappedKGCommunitiesResponseV3,
    WrappedKGCreationResponse as WrappedKGCreationResponseV3,
    WrappedKGEnrichmentResponse as WrappedKGEnrichmentResponseV3,
    WrappedKGTunePromptResponse as WrappedKGTunePromptResponseV3,
    WrappedKGEntityDeduplicationResponse as WrappedKGEntityDeduplicationResponseV3,
    WrappedKGDeletionResponse as WrappedKGDeletionResponseV3,
    KGCreationResponse as KGCreationResponseV3,
    KGEnrichmentResponse as KGEnrichmentResponseV3,
    KGEntityDeduplicationResponse as KGEntityDeduplicationResponseV3,
    KGTunePromptResponse as KGTunePromptResponseV3,
    KGDeletionResponse as KGDeletionResponseV3,
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
    # Knowledge Graph Responses for V2
    # will be removed eventually
    "KGCreationResponse",
    "WrappedKGCreationResponse",
    "KGEnrichmentResponse",
    "WrappedKGEnrichmentResponse",
    "KGEntityDeduplicationResponse",
    "WrappedKGEntityDeduplicationResponse",
    "WrappedKGTunePromptResponse",
    # Knowledge Graph Responses for V3
    "WrappedKGEntitiesResponseV3",
    "WrappedKGRelationshipsResponseV3",
    "WrappedKGCommunitiesResponseV3",
    "WrappedKGCreationResponseV3",
    "WrappedKGEnrichmentResponseV3",
    "WrappedKGTunePromptResponseV3",
    "WrappedKGEntityDeduplicationResponseV3",
    "KGCreationResponseV3",
    "KGEnrichmentResponseV3",
    "KGEntityDeduplicationResponseV3",
    "KGTunePromptResponseV3",
    "WrappedKGDeletionResponseV3",
    "KGDeletionResponseV3",
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
