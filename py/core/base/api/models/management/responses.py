from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel

from core.base.api.models.base import ResultsWrapper


class UpdatePromptResponse(BaseModel):
    message: str


class PromptResponse(BaseModel):
    name: str
    template: str
    created_at: datetime
    updated_at: datetime
    input_types: Dict[str, str]


class AllPromptsResponse(BaseModel):
    prompts: Dict[str, PromptResponse]


class LogEntry(BaseModel):
    key: str
    value: Any
    timestamp: datetime


class LogResponse(BaseModel):
    run_id: UUID
    run_type: str
    entries: List[LogEntry]
    timestamp: Optional[datetime]
    user_id: Optional[UUID]


class ServerStats(BaseModel):
    start_time: datetime
    uptime_seconds: float
    cpu_usage: float
    memory_usage: float


class AnalyticsResponse(BaseModel):
    analytics_data: Optional[dict] = None
    filtered_logs: Dict[str, Any]


class AppSettingsResponse(BaseModel):
    config: Dict[str, Any]
    prompts: Dict[str, Any]


class ScoreCompletionResponse(BaseModel):
    message: str


class UserOverviewResponse(BaseModel):
    user_id: UUID
    num_files: int
    total_size_in_bytes: int
    document_ids: List[UUID]


class DocumentOverviewResponse(BaseModel):
    id: UUID
    title: str
    user_id: UUID
    type: str
    created_at: datetime
    updated_at: datetime
    ingestion_status: str
    restructuring_status: str
    version: str
    collection_ids: list[UUID]
    metadata: Dict[str, Any]


class DocumentChunkResponse(BaseModel):
    fragment_id: UUID
    extraction_id: UUID
    document_id: UUID
    user_id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: Dict[str, Any]


KnowledgeGraphResponse = str


class GroupResponse(BaseModel):
    collection_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class GroupOverviewResponse(BaseModel):
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
WrappedLogResponse = ResultsWrapper[List[LogResponse]]
WrappedAnalyticsResponse = ResultsWrapper[AnalyticsResponse]
WrappedAppSettingsResponse = ResultsWrapper[AppSettingsResponse]
WrappedScoreCompletionResponse = ResultsWrapper[ScoreCompletionResponse]
WrappedUserOverviewResponse = ResultsWrapper[List[UserOverviewResponse]]
WrappedDocumentOverviewResponse = ResultsWrapper[
    List[DocumentOverviewResponse]
]
WrappedDocumentChunkResponse = ResultsWrapper[List[DocumentChunkResponse]]
WrappedKnowledgeGraphResponse = ResultsWrapper[KnowledgeGraphResponse]
WrappedCollectionResponse = ResultsWrapper[GroupResponse]
WrappedCollectionListResponse = ResultsWrapper[List[GroupResponse]]
WrappedCollectionOverviewResponse = ResultsWrapper[List[GroupOverviewResponse]]
WrappedAddUserResponse = ResultsWrapper[AddUserResponse]
