from typing import Any, Dict, Generic, List, TypeVar
from uuid import UUID

from pydantic import BaseModel

from r2r.base.api.models.base import ResultsWrapper

T = TypeVar("T")


class ProcessedDocument(BaseModel):
    id: UUID
    title: str


class FailedDocument(BaseModel):
    document_id: UUID
    result: Any


class IngestionResponse(BaseModel):
    processed_documents: List[ProcessedDocument]
    failed_documents: List[FailedDocument]
    skipped_documents: List[UUID]


# Create wrapped version of the response
WrappedIngestionResponse = ResultsWrapper[IngestionResponse]
