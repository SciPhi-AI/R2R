from datetime import datetime
from typing import Any, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from shared.api.models.base import ResultsWrapper

T = TypeVar("T")


class DocumentIngestionResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the ingestion request.",
    )
    task_id: Optional[UUID] = Field(
        None,
        description="The task ID of the ingestion request.",
    )
    document_id: UUID = Field(
        ...,
        description="The ID of the document that was ingested.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Ingestion task queued successfully.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
            }
        }


class DocumentResponse(BaseModel):
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
