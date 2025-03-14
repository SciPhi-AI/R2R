from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions.document import DocumentResponse
from shared.abstractions.llm import Message
from shared.abstractions.user import Token, User
from shared.api.models.base import PaginatedR2RResult, R2RResults


class PromptResponse(BaseModel):
    id: UUID
    name: str
    template: str
    created_at: datetime
    updated_at: datetime
    input_types: dict[str, str]


class ServerStats(BaseModel):
    start_time: datetime
    uptime_seconds: float
    cpu_usage: float
    memory_usage: float


class SettingsResponse(BaseModel):
    config: dict[str, Any]
    prompts: dict[str, Any]
    r2r_project_name: str
    # r2r_version: str


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


class LoginResponse(BaseModel):
    access_token: Token
    refresh_token: Token


class UsageLimit(BaseModel):
    used: int
    limit: int
    remaining: int


class StorageTypeLimit(BaseModel):
    limit: int
    used: int
    remaining: int


class StorageLimits(BaseModel):
    chunks: StorageTypeLimit
    documents: StorageTypeLimit
    collections: StorageTypeLimit


class RouteUsage(BaseModel):
    route_per_min: UsageLimit
    monthly_limit: UsageLimit


class Usage(BaseModel):
    global_per_min: UsageLimit
    monthly_limit: UsageLimit
    routes: dict[str, RouteUsage]


class SystemDefaults(BaseModel):
    global_per_min: int
    route_per_min: Optional[int]
    monthly_limit: int


class LimitsResponse(BaseModel):
    storage_limits: StorageLimits
    system_defaults: SystemDefaults
    user_overrides: dict
    effective_limits: SystemDefaults
    usage: Usage


# Chunk Responses
WrappedChunkResponse = R2RResults[ChunkResponse]
WrappedChunksResponse = PaginatedR2RResult[list[ChunkResponse]]

# Collection Responses
WrappedCollectionResponse = R2RResults[CollectionResponse]
WrappedCollectionsResponse = PaginatedR2RResult[list[CollectionResponse]]

# Conversation Responses
WrappedConversationMessagesResponse = R2RResults[list[MessageResponse]]
WrappedConversationResponse = R2RResults[ConversationResponse]
WrappedConversationsResponse = PaginatedR2RResult[list[ConversationResponse]]
WrappedMessageResponse = R2RResults[MessageResponse]
WrappedMessagesResponse = PaginatedR2RResult[list[MessageResponse]]

# Document Responses
WrappedDocumentResponse = R2RResults[DocumentResponse]
WrappedDocumentsResponse = PaginatedR2RResult[list[DocumentResponse]]

# Prompt Responses
WrappedPromptResponse = R2RResults[PromptResponse]
WrappedPromptsResponse = PaginatedR2RResult[list[PromptResponse]]

# System Responses
WrappedSettingsResponse = R2RResults[SettingsResponse]
WrappedServerStatsResponse = R2RResults[ServerStats]

# User Responses
WrappedUserResponse = R2RResults[User]
WrappedUsersResponse = PaginatedR2RResult[list[User]]
WrappedAPIKeyResponse = R2RResults[ApiKey]
WrappedAPIKeysResponse = PaginatedR2RResult[list[ApiKeyNoPriv]]
WrappedLoginResponse = R2RResults[LoginResponse]
WrappedLimitsResponse = R2RResults[LimitsResponse]
