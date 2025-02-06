from typing import Any, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

from shared.api.models.base import PaginatedR2RResult, R2RResults

T = TypeVar("T")


class IngestionResponse(BaseModel):
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


class UpdateResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the ingestion request.",
    )
    task_id: Optional[UUID] = Field(
        None,
        description="The task ID of the ingestion request.",
    )
    document_ids: list[UUID] = Field(
        ...,
        description="The ID of the document that was ingested.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Update task queued successfully.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                "document_ids": ["9fbe403b-c11c-5aae-8ade-ef22980c3ad1"],
            }
        }


class VectorIndexResponse(BaseModel):
    index: dict[str, Any]


class VectorIndicesResponse(BaseModel):
    indices: list[VectorIndexResponse]


WrappedIngestionResponse = R2RResults[IngestionResponse]
WrappedMetadataUpdateResponse = R2RResults[IngestionResponse]
WrappedUpdateResponse = R2RResults[UpdateResponse]

WrappedVectorIndexResponse = R2RResults[VectorIndexResponse]
WrappedVectorIndicesResponse = PaginatedR2RResult[VectorIndicesResponse]
