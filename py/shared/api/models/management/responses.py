from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper
from shared.abstractions.document import DocumentInfo

from shared.abstractions.llm import Message


class UpdatePromptResponse(BaseModel):
    message: str


class PromptResponse(BaseModel):
    prompt_id: UUID
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


class AppSettingsResponse(BaseModel):
    config: dict[str, Any]
    prompts: dict[str, Any]


class ScoreCompletionResponse(BaseModel):
    message: str


# TODO: This should just be a UserResponse...
class UserOverviewResponse(BaseModel):
    user_id: UUID
    num_files: int
    total_size_in_bytes: int
    document_ids: list[UUID]


# FIXME: Why are we redefining this and not using the model in py/shared/api/models/auth/responses.py?
class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_verified: bool = False
    collection_ids: list[UUID] = []

    # Optional fields (to update or set at creation)
    hashed_password: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


class DocumentOverviewResponse(BaseModel):
    id: UUID
    title: str
    user_id: UUID
    document_type: str
    created_at: datetime
    updated_at: datetime
    ingestion_status: str
    kg_extraction_status: str
    version: str
    collection_ids: list[UUID]
    metadata: dict[str, Any]


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None


class CollectionResponse(BaseModel):
    collection_id: UUID
    user_id: Optional[UUID]
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    user_count: int
    document_count: int


class ConversationResponse(BaseModel):
    id: UUID
    created_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    message: Message


class BranchResponse(BaseModel):
    branch_id: UUID
    branch_point_id: Optional[UUID]
    content: Optional[str]
    created_at: datetime


class AddUserResponse(BaseModel):
    result: bool


# Collection Responses
WrappedCollectionResponse = ResultsWrapper[CollectionResponse]
WrappedCollectionsResponse = PaginatedResultsWrapper[list[CollectionResponse]]


# Conversation Responses
WrappedConversationResponse = ResultsWrapper[ConversationResponse]
WrappedConversationsResponse = PaginatedResultsWrapper[
    list[ConversationResponse]
]

WrappedMessageResponse = ResultsWrapper[MessageResponse]
WrappedMessagesResponse = PaginatedResultsWrapper[list[MessageResponse]]

WrappedBranchResponse = ResultsWrapper[BranchResponse]
WrappedBranchesResponse = PaginatedResultsWrapper[list[BranchResponse]]


# Prompt Responses
WrappedPromptResponse = ResultsWrapper[PromptResponse]
WrappedPromptsResponse = PaginatedResultsWrapper[list[PromptResponse]]

# User Responses
WrappedUserOverviewResponse = ResultsWrapper[UserOverviewResponse]
WrappedUsersOverviewResponse = PaginatedResultsWrapper[
    list[UserOverviewResponse]
]

# TODO: anything below this hasn't been reviewed
WrappedServerStatsResponse = ResultsWrapper[ServerStats]
WrappedLogResponse = ResultsWrapper[list[LogResponse]]
WrappedAnalyticsResponse = ResultsWrapper[AnalyticsResponse]
WrappedAppSettingsResponse = ResultsWrapper[AppSettingsResponse]


# FIXME: Do we really need DocumentInfo and DocumentOverviewResponse? Can it just be a DocumentResponse?
WrappedDocumentResponse = PaginatedResultsWrapper[list[DocumentInfo]]
WrappedDocumentOverviewResponse = PaginatedResultsWrapper[
    list[DocumentOverviewResponse]
]
WrappedPromptMessageResponse = ResultsWrapper[UpdatePromptResponse]

WrappedAddUserResponse = ResultsWrapper[None]
WrappedUsersInCollectionResponse = PaginatedResultsWrapper[list[UserResponse]]
WrappedUserCollectionResponse = PaginatedResultsWrapper[
    list[CollectionResponse]
]

WrappedDocumentChunkResponse = ResultsWrapper[DocumentChunkResponse]
WrappedDocumentChunksResponse = PaginatedResultsWrapper[
    list[DocumentChunkResponse]
]
WrappedDeleteResponse = ResultsWrapper[None]
