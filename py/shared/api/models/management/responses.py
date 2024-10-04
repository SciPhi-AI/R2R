from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper


class UpdatePromptResponse(BaseModel):
    message: str


class PromptResponse(BaseModel):
    name: str
    template: str
    created_at: datetime
    updated_at: datetime
    input_types: dict[str, str]


class AllPromptsResponse(BaseModel):
    prompts: dict[str, PromptResponse]


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


class UserOverviewResponse(BaseModel):
    user_id: UUID
    num_files: int
    total_size_in_bytes: int
    document_ids: list[UUID]


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
    type: str
    created_at: datetime
    updated_at: datetime
    ingestion_status: str
    kg_extraction_status: str
    version: str
    collection_ids: list[UUID]
    metadata: dict[str, Any]


class DocumentChunkResponse(BaseModel):
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]


KnowledgeGraphResponse = str


class CollectionResponse(BaseModel):
    collection_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class CollectionOverviewResponse(BaseModel):
    collection_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    user_count: int
    document_count: int


class AddUserResponse(BaseModel):
    result: bool


# Create wrapped versions of each response
WrappedPromptMessageResponse = ResultsWrapper[UpdatePromptResponse]
WrappedGetPromptsResponse = ResultsWrapper[AllPromptsResponse]
WrappedServerStatsResponse = ResultsWrapper[ServerStats]
WrappedLogResponse = ResultsWrapper[list[LogResponse]]
WrappedAnalyticsResponse = ResultsWrapper[AnalyticsResponse]
WrappedAppSettingsResponse = ResultsWrapper[AppSettingsResponse]
WrappedScoreCompletionResponse = ResultsWrapper[ScoreCompletionResponse]
WrappedUserOverviewResponse = PaginatedResultsWrapper[
    list[UserOverviewResponse]
]
WrappedDocumentOverviewResponse = PaginatedResultsWrapper[
    list[DocumentOverviewResponse]
]
WrappedKnowledgeGraphResponse = ResultsWrapper[KnowledgeGraphResponse]
WrappedCollectionResponse = ResultsWrapper[CollectionResponse]
WrappedCollectionListResponse = ResultsWrapper[list[CollectionResponse]]
WrappedCollectionOverviewResponse = ResultsWrapper[
    list[CollectionOverviewResponse]
]
WrappedAddUserResponse = ResultsWrapper[AddUserResponse]
WrappedUsersInCollectionResponse = PaginatedResultsWrapper[list[UserResponse]]
WrappedUserCollectionResponse = PaginatedResultsWrapper[
    list[CollectionOverviewResponse]
]
WrappedDocumentChunkResponse = PaginatedResultsWrapper[
    list[DocumentChunkResponse]
]
WrappedDeleteResponse = ResultsWrapper[None]
