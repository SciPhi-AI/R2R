from typing import Union
from uuid import UUID

from pydantic import BaseModel, Field

from shared.abstractions.base import R2RSerializable
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


class KGCreationEstimationResponse(R2RSerializable):
    """Response for knowledge graph creation estimation."""

    message: str = Field(
        default="",
        description="The message to display to the user.",
    )

    document_count: int = Field(
        default=-1,
        description="The number of documents in the collection.",
    )

    number_of_jobs_created: int = Field(
        default=-1,
        description="The number of jobs created for the graph creation process.",
    )

    total_chunks: int = Field(
        default=-1,
        description="The estimated total number of chunks.",
    )

    estimated_entities: str = Field(
        default="NA",
        description="The estimated number of entities in the graph.",
    )

    estimated_triples: str = Field(
        default="NA",
        description="The estimated number of triples in the graph.",
    )

    estimated_llm_calls: str = Field(
        default="NA",
        description="The estimated number of LLM calls in millions.",
    )

    estimated_total_in_out_tokens_in_millions: str = Field(
        default="NA",
        description="The estimated total number of input and output tokens in millions.",
    )

    estimated_total_time_in_minutes: str = Field(
        default="NA",
        description="The estimated total time to run the graph creation process in minutes.",
    )

    estimated_cost_in_usd: str = Field(
        default="NA",
        description="The estimated cost to run the graph creation process in USD.",
    )


class KGEnrichmentEstimationResponse(R2RSerializable):
    """Response for knowledge graph enrichment estimation."""

    message: str = Field(
        default="",
        description="The message to display to the user.",
    )

    total_entities: int = Field(
        default=-1,
        description="The total number of entities in the graph.",
    )

    total_triples: int = Field(
        default=-1,
        description="The total number of triples in the graph.",
    )

    estimated_llm_calls: str = Field(
        default="NA",
        description="The estimated number of LLM calls.",
    )

    estimated_total_in_out_tokens_in_millions: str = Field(
        default="NA",
        description="The estimated total number of input and output tokens in millions.",
    )

    estimated_cost_in_usd: str = Field(
        default="NA",
        description="The estimated cost to run the graph enrichment process.",
    )

    estimated_total_time_in_minutes: str = Field(
        default="NA",
        description="The estimated total time to run the graph enrichment process.",
    )


WrappedKGCreationResponse = ResultsWrapper[
    Union[KGCreationResponse, KGCreationEstimationResponse]
]
WrappedKGEnrichmentResponse = ResultsWrapper[
    Union[KGEnrichmentResponse, KGEnrichmentEstimationResponse]
]
