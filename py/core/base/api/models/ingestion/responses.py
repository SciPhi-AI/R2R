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
    processed_documents: List[ProcessedDocument] = Field(
        ...,
        description="List of successfully processed documents",
        example=[
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Document 1",
            },
            {
                "id": "223e4567-e89b-12d3-a456-426614174000",
                "title": "Document 2",
            },
        ],
    )
    failed_documents: List[FailedDocument] = Field(
        ...,
        description="List of documents that failed to process",
        example=[
            {
                "document_id": "323e4567-e89b-12d3-a456-426614174000",
                "result": "Error: Invalid format",
            }
        ],
    )
    skipped_documents: List[UUID] = Field(
        ...,
        description="List of document IDs that were skipped during processing",
        example=["423e4567-e89b-12d3-a456-426614174000"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "processed_documents": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "title": "Document 1",
                    },
                    {
                        "id": "223e4567-e89b-12d3-a456-426614174000",
                        "title": "Document 2",
                    },
                ],
                "failed_documents": [
                    {
                        "document_id": "323e4567-e89b-12d3-a456-426614174000",
                        "result": "Error: Invalid format",
                    }
                ],
                "skipped_documents": ["423e4567-e89b-12d3-a456-426614174000"],
            }
        }


# Create wrapped version of the response
WrappedIngestionResponse = ResultsWrapper[IngestionResponse]
