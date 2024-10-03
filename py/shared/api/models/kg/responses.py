from uuid import UUID

from pydantic import BaseModel, Field

from shared.api.models.base import ResultsWrapper


class KGCreationResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the KG creation request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the KG creation request.",
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
        description="A message describing the result of the KG enrichment request.",
    )
    task_id: UUID = Field(
        ...,
        description="The task ID of the KG enrichment request.",
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
