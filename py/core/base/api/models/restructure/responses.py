from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field

from core.base.api.models.base import ResultsWrapper


class KGCreationResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the restructure request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the restructure request.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Graph creation queued successfully.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            }
        }


class KGEnrichmentResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the restructure request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the restructure request.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Graph enrichment queued successfuly.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            }
        }


WrappedKGCreationResponse = ResultsWrapper[KGCreationResponse]
WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]
