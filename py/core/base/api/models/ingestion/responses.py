from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from core.base.api.models.base import ResultsWrapper

T = TypeVar("T")


class IngestionResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the ingestion request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the ingestion request.",
    )
    document_id: UUID = Field(
        ...,
        description="The ID of the document that was ingested.",
    )


WrappedIngestionResponse = ResultsWrapper[list[IngestionResponse]]
