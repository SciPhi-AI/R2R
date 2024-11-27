from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions import R2RSerializable
from shared.abstractions.document import DocumentResponse
from shared.abstractions.llm import Message
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper


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
    run_type: str
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
    r2r_project_name: str
    # r2r_version: str


class UserResponse(R2RSerializable):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_verified: bool = False
    collection_ids: list[UUID] = []
    graph_ids: list[UUID] = []

    # Optional fields (to update or set at creation)
    hashed_password: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None


class CollectionResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    name: str
    description: Optional[str]
    graph_cluster_status: str
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


class BranchResponse(BaseModel):
    branch_id: UUID
    branch_point_id: Optional[UUID]
    content: Optional[str]
    created_at: datetime
    user_id: Optional[UUID] = None
    name: Optional[str] = None


# Chunk Responses
WrappedChunkResponse = ResultsWrapper[ChunkResponse]
WrappedChunksResponse = PaginatedResultsWrapper[list[ChunkResponse]]

# Collection Responses
WrappedCollectionResponse = ResultsWrapper[CollectionResponse]
WrappedCollectionsResponse = PaginatedResultsWrapper[list[CollectionResponse]]


# Conversation Responses
WrappedConversationMessagesResponse = ResultsWrapper[list[MessageResponse]]
WrappedConversationResponse = ResultsWrapper[ConversationResponse]
WrappedConversationsResponse = PaginatedResultsWrapper[
    list[ConversationResponse]
]
WrappedMessageResponse = ResultsWrapper[MessageResponse]
WrappedMessagesResponse = PaginatedResultsWrapper[list[MessageResponse]]
WrappedBranchResponse = ResultsWrapper[BranchResponse]
WrappedBranchesResponse = PaginatedResultsWrapper[list[BranchResponse]]

# Document Responses
WrappedDocumentResponse = ResultsWrapper[DocumentResponse]
WrappedDocumentsResponse = PaginatedResultsWrapper[list[DocumentResponse]]

# Prompt Responses
WrappedPromptResponse = ResultsWrapper[PromptResponse]
WrappedPromptsResponse = PaginatedResultsWrapper[list[PromptResponse]]

# System Responses
WrappedSettingsResponse = ResultsWrapper[SettingsResponse]
WrappedServerStatsResponse = ResultsWrapper[ServerStats]

# User Responses
WrappedUserResponse = ResultsWrapper[UserResponse]
WrappedUsersResponse = PaginatedResultsWrapper[list[UserResponse]]

# TODO: anything below this hasn't been reviewed
WrappedLogsResponse = ResultsWrapper[list[LogResponse]]
WrappedAnalyticsResponse = ResultsWrapper[AnalyticsResponse]
WrappedVerificationResult = ResultsWrapper[VerificationResult]
WrappedResetDataResult = ResultsWrapper[ResetDataResult]
