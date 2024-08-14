import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from r2r.base.logging.log_processor import AnalysisTypes, LogFilterCriteria


class R2RUpdatePromptRequest(BaseModel):
    name: str
    template: Optional[str] = None
    input_types: Optional[dict[str, str]] = {}


class R2RDeleteRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class R2RAnalyticsRequest(BaseModel):
    filter_criteria: LogFilterCriteria
    analysis_types: AnalysisTypes


class R2RUsersOverviewRequest(BaseModel):
    user_ids: Optional[list[uuid.UUID]]


class R2RDocumentsOverviewRequest(BaseModel):
    document_ids: Optional[list[uuid.UUID]]


class R2RDocumentChunksRequest(BaseModel):
    document_id: uuid.UUID


class R2RLogsRequest(BaseModel):
    run_type_filter: Optional[str] = (None,)
    max_runs_requested: int = 100


class R2RPrintRelationshipsRequest(BaseModel):
    limit: int = 100


class R2RCreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class R2RUpdateGroupRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class R2RAddUserToGroupRequest(BaseModel):
    user_id: uuid.UUID
    group_id: uuid.UUID


class R2RRemoveUserFromGroupRequest(BaseModel):
    user_id: uuid.UUID
    group_id: uuid.UUID


class R2RGroupsOverviewRequest(BaseModel):
    group_ids: Optional[list[uuid.UUID]]


class R2RScoreCompletionRequest(BaseModel):
    message_id: uuid.UUID = None
    score: float = None


class R2RAssignDocumentToGroupRequest(BaseModel):
    document_id: str
    group_id: uuid.UUID


class R2RRemoveDocumentFromGroupRequest(BaseModel):
    document_id: str
    group_id: uuid.UUID
