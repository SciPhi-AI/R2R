from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from shared.abstractions.base import R2RSerializable
from shared.abstractions.graph import Community, Entity, Relationship
from shared.api.models.base import ResultsWrapper, PaginatedResultsWrapper


############# ESTIMATE MODELS #############


class KGCreationEstimate(R2RSerializable):
    """Response for knowledge graph creation estimation."""

    document_count: Optional[int] = Field(
        default=None,
        description="The number of documents in the collection.",
    )

    number_of_jobs_created: Optional[int] = Field(
        default=None,
        description="The number of jobs created for the graph creation process.",
    )

    total_chunks: Optional[int] = Field(
        default=None,
        description="The estimated total number of chunks.",
    )

    estimated_entities: Optional[str] = Field(
        default=None,
        description="The estimated number of entities in the graph.",
    )

    estimated_relationships: Optional[str] = Field(
        default=None,
        description="The estimated number of relationships in the graph.",
    )

    estimated_llm_calls: Optional[str] = Field(
        default=None,
        description="The estimated number of LLM calls in millions.",
    )

    estimated_total_in_out_tokens_in_millions: Optional[str] = Field(
        default=None,
        description="The estimated total number of input and output tokens in millions.",
    )

    estimated_total_time_in_minutes: Optional[str] = Field(
        default=None,
        description="The estimated total time to run the graph creation process in minutes.",
    )

    estimated_cost_in_usd: Optional[str] = Field(
        default=None,
        description="The estimated cost to run the graph creation process in USD.",
    )


class KGEnrichmentEstimate(BaseModel):
    total_entities: Optional[int] = Field(
        default=None,
        description="The total number of entities in the graph.",
    )

    total_relationships: Optional[int] = Field(
        default=None,
        description="The total number of relationships in the graph.",
    )

    estimated_llm_calls: Optional[str] = Field(
        default=None,
        description="The estimated number of LLM calls.",
    )

    estimated_total_in_out_tokens_in_millions: Optional[str] = Field(
        default=None,
        description="The estimated total number of input and output tokens in millions.",
    )

    estimated_cost_in_usd: Optional[str] = Field(
        default=None,
        description="The estimated cost to run the graph enrichment process.",
    )

    estimated_total_time_in_minutes: Optional[str] = Field(
        default=None,
        description="The estimated total time to run the graph enrichment process.",
    )


class KGDeduplicationEstimate(R2RSerializable):
    """Response for knowledge graph deduplication estimation."""

    num_entities: Optional[int] = Field(
        default=None,
        description="The number of entities in the collection.",
    )

    estimated_llm_calls: Optional[str] = Field(
        default=None,
        description="The estimated number of LLM calls.",
    )

    estimated_total_in_out_tokens_in_millions: Optional[str] = Field(
        default=None,
        description="The estimated total number of input and output tokens in millions.",
    )

    estimated_cost_in_usd: Optional[str] = Field(
        default=None,
        description="The estimated cost in USD.",
    )

    estimated_total_time_in_minutes: Optional[str] = Field(
        default=None,
        description="The estimated time in minutes.",
    )


############# RESPONSE MODELS #############


class KGCreationResponse(BaseModel):
    message: str = Field(
        ...,
        description="A message describing the result of the KG creation request.",
    )
    id: Optional[UUID] = Field(
        None,
        description="The ID of the created object.",
    )
    task_id: Optional[UUID] = Field(
        None,
        description="The task ID of the KG creation request.",
    )
    estimate: Optional[KGCreationEstimate] = Field(
        None,
        description="The estimation of the KG creation request.",
    )


class Config:
    json_schema_extra = {
        "example": {
            "message": "Graph creation queued successfully.",
            "id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            "estimate": {
                "document_count": 100,
                "number_of_jobs_created": 10,
                "total_chunks": 1000,
                "estimated_entities": "1000",
                "estimated_relationships": "1000",
                "estimated_llm_calls": "1000",
                "estimated_total_in_out_tokens_in_millions": "1000",
                "estimated_total_time_in_minutes": "1000",
                "estimated_cost_in_usd": "1000",
            },
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
    estimate: Optional[KGEnrichmentEstimate] = Field(
        None,
        description="The estimation of the KG enrichment request.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Graph enrichment queued successfuly.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                "estimate": {
                    "total_entities": 1000,
                    "total_relationships": 1000,
                    "estimated_llm_calls": "1000",
                    "estimated_total_in_out_tokens_in_millions": "1000",
                    "estimated_cost_in_usd": "1000",
                    "estimated_total_time_in_minutes": "1000",
                },
            }
        }


class KGEntityDeduplicationResponse(BaseModel):
    """Response for knowledge graph entity deduplication."""

    message: str = Field(
        ...,
        description="The message to display to the user.",
    )

    task_id: Optional[UUID] = Field(
        None,
        description="The task ID of the KG entity deduplication request.",
    )

    estimate: Optional[KGDeduplicationEstimate] = Field(
        None,
        description="The estimation of the KG entity deduplication request.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Entity deduplication queued successfully.",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                "estimate": {
                    "num_entities": 1000,
                    "estimated_llm_calls": "1000",
                    "estimated_total_in_out_tokens_in_millions": "1000",
                    "estimated_cost_in_usd": "1000",
                    "estimated_total_time_in_minutes": "1000",
                },
            }
        }


class KGDeletionResponse(BaseModel):
    """Response for knowledge graph deletion."""

    message: str = Field(
        ...,
        description="The message to display to the user.",
    )
    id: UUID = Field(
        ...,
        description="The ID of the deleted graph.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Entity deleted successfully.",
                "id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }



class KGTunePromptResponse(R2RSerializable):
    """Response containing just the tuned prompt string."""

    tuned_prompt: str = Field(
        ...,
        description="The updated prompt.",
    )

    class Config:
        json_schema_extra = {"example": {"tuned_prompt": "The updated prompt"}}


# GET
WrappedKGEntitiesResponse = PaginatedResultsWrapper[list[Entity]]
WrappedKGRelationshipsResponse = PaginatedResultsWrapper[list[Relationship]]
WrappedKGCommunitiesResponse = PaginatedResultsWrapper[list[Community]]


# CREATE
WrappedKGCreationResponse = ResultsWrapper[KGCreationResponse]
WrappedKGEnrichmentResponse = ResultsWrapper[KGEnrichmentResponse]


WrappedKGTunePromptResponse = ResultsWrapper[KGTunePromptResponse]
WrappedKGEntityDeduplicationResponse = ResultsWrapper[
    KGEntityDeduplicationResponse
]
WrappedKGDeletionResponse = ResultsWrapper[KGDeletionResponse]