import uuid
from typing import Optional, Union

from pydantic import BaseModel

from r2r.base import (
    AnalysisTypes,
    Document,
    FilterCriteria,
    GenerationConfig,
    KGSearchSettings,
    VectorSearchSettings,
)


class R2RUpdatePromptRequest(BaseModel):
    name: str
    template: Optional[str] = None
    input_types: Optional[dict[str, str]] = {}


class R2RIngestDocumentsRequest(BaseModel):
    documents: list[Document]
    versions: Optional[list[str]] = None

    class Config:
        arbitrary_types_allowed = True


class R2RUpdateDocumentsRequest(BaseModel):
    documents: list[Document]
    versions: Optional[list[str]] = None
    metadatas: Optional[list[dict]] = None


class R2RIngestFilesRequest(BaseModel):
    metadatas: Optional[list[dict]] = None
    document_ids: Optional[list[uuid.UUID]] = None
    user_ids: Optional[list[Optional[uuid.UUID]]] = None
    versions: Optional[list[str]] = None


class R2RUpdateFilesRequest(BaseModel):
    metadatas: Optional[list[dict]] = None
    document_ids: Optional[list[uuid.UUID]] = None


class R2RSearchRequest(BaseModel):
    query: str
    vector_search_settings: Optional[VectorSearchSettings] = None
    kg_search_settings: Optional[KGSearchSettings] = None


class R2RRAGRequest(BaseModel):
    query: str
    vector_search_settings: Optional[VectorSearchSettings] = None
    kg_search_settings: Optional[KGSearchSettings] = None
    rag_generation_config: Optional[GenerationConfig] = None


class R2REvalRequest(BaseModel):
    query: str
    context: str
    completion: str


class R2RDeleteRequest(BaseModel):
    keys: list[str]
    values: list[Union[bool, int, str]]


class R2RAnalyticsRequest(BaseModel):
    filter_criteria: FilterCriteria
    analysis_types: AnalysisTypes


class R2RUsersOverviewRequest(BaseModel):
    user_ids: Optional[list[uuid.UUID]]


class R2RDocumentsOverviewRequest(BaseModel):
    document_ids: Optional[list[uuid.UUID]]
    user_ids: Optional[list[uuid.UUID]]


class R2RDocumentChunksRequest(BaseModel):
    document_id: uuid.UUID


class R2RLogsRequest(BaseModel):
    log_type_filter: Optional[str] = (None,)
    max_runs_requested: int = 100
