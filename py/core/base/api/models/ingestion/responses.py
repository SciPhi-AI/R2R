from typing import Any, TypeVar
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
    message: str = Field(
        ...,
        description="A message describing the result of the ingestion request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the ingestion request.",
    )


WrappedIngestionResponse = ResultsWrapper[IngestionResponse]
