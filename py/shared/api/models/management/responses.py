from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.document import DocumentResponse
from shared.abstractions.llm import Message
from shared.abstractions.user import User
from shared.api.models.base import PaginatedFUSEResult, FUSEResults


class PromptResponse(BaseModel):
    id: UUID
    name: str
    template: str
    created_at: datetime
    updated_at: datetime
    input_types: dict[str, str]


class LogEntry(BaseModel):
    key: str
    value: Any
    timestamp: datetime


class LogResponse(BaseModel):
    run_id: UUID
    entries: list[LogEntry]
    timestamp: Optional[datetime]
    user_id: Optional[UUID]


class ServerStats(BaseModel):
    start_time: datetime
    uptime_seconds: float
    cpu_usage: float
    memory_usage: float


class AnalyticsResponse(BaseModel):
    analytics_data: Optional[dict] = None
    filtered_logs: dict[str, Any]


class SettingsResponse(BaseModel):
    config: dict[str, Any]
    prompts: dict[str, Any]
    fuse_project_name: str
    # fuse_version: str


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    owner_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None


class CollectionResponse(BaseModel):
    id: UUID
    owner_id: Optional[UUID]
    name: str
    description: Optional[str]
    graph_cluster_status: str
    graph_sync_status: str
    created_at: datetime
    updated_at: datetime
    user_count: int
    document_count: int


class ConversationResponse(BaseModel):
    id: UUID
    created_at: datetime
    user_id: Optional[UUID] = None
    name: Optional[str] = None


class VerificationResult(BaseModel):
    verification_code: str
    expiry: datetime
    message: Optional[str] = None


class ResetDataResult(BaseModel):
    reset_token: str
    expiry: datetime
    message: Optional[str] = None


class MessageResponse(BaseModel):
    id: UUID
    message: Message
    metadata: dict[str, Any] = {}


class ApiKey(BaseModel):
    public_key: str
    api_key: str
    key_id: str
    name: Optional[str] = None


class ApiKeyNoPriv(BaseModel):
    public_key: str
    key_id: str
    name: Optional[str] = None
    updated_at: datetime
    description: Optional[str] = None


# Chunk Responses
WrappedChunkResponse = FUSEResults[ChunkResponse]
WrappedChunksResponse = PaginatedFUSEResult[list[ChunkResponse]]

# Collection Responses
WrappedCollectionResponse = FUSEResults[CollectionResponse]
WrappedCollectionsResponse = PaginatedFUSEResult[list[CollectionResponse]]


# Conversation Responses
WrappedConversationMessagesResponse = FUSEResults[list[MessageResponse]]
WrappedConversationResponse = FUSEResults[ConversationResponse]
WrappedConversationsResponse = PaginatedFUSEResult[list[ConversationResponse]]
WrappedMessageResponse = FUSEResults[MessageResponse]
WrappedMessagesResponse = PaginatedFUSEResult[list[MessageResponse]]

# Document Responses
WrappedDocumentResponse = FUSEResults[DocumentResponse]
WrappedDocumentsResponse = PaginatedFUSEResult[list[DocumentResponse]]

# Prompt Responses
WrappedPromptResponse = FUSEResults[PromptResponse]
WrappedPromptsResponse = PaginatedFUSEResult[list[PromptResponse]]

# System Responses
WrappedSettingsResponse = FUSEResults[SettingsResponse]
WrappedServerStatsResponse = FUSEResults[ServerStats]

# User Responses
WrappedUserResponse = FUSEResults[User]
WrappedUsersResponse = PaginatedFUSEResult[list[User]]
WrappedAPIKeyResponse = FUSEResults[ApiKey]
WrappedAPIKeysResponse = PaginatedFUSEResult[list[ApiKeyNoPriv]]

# TODO: anything below this hasn't been reviewed
WrappedLogsResponse = FUSEResults[list[LogResponse]]
WrappedAnalyticsResponse = FUSEResults[AnalyticsResponse]
WrappedVerificationResult = FUSEResults[VerificationResult]
WrappedResetDataResult = FUSEResults[ResetDataResult]
