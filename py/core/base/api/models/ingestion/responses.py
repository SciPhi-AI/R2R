from typing import Any, List, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from core.base.api.models.base import ResultsWrapper

T = TypeVar("T")


class ProcessedDocument(BaseModel):
    id: UUID
    title: str


class FailedDocument(BaseModel):
    document_id: UUID
    result: Any


class IngestionResponse(BaseModel):
    message: str = Field(..., description="A message describing the result of the ingestion request.")

# Create wrapped version of the response
WrappedIngestionResponse = ResultsWrapper[IngestionResponse]
