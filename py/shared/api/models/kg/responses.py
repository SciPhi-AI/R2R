from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from shared.abstractions.base import R2RSerializable
from shared.api.models.base import ResultsWrapper
from shared.abstractions.graph import Entity, Triple, CommunityReport


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

    estimated_triples: Optional[str] = Field(
        default=None,
        description="The estimated number of triples in the graph.",
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


class KGEnrichmentEstimationResponse(R2RSerializable):
    """Response for knowledge graph enrichment estimation."""

    message: str = Field(
        default="",
        description="The message to display to the user.",
    )

    total_entities: Optional[int] = Field(
        default=None,
        description="The total number of entities in the graph.",
    )

    total_triples: Optional[int] = Field(
        default=None,
        description="The total number of triples in the graph.",
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


class KGEntitiesResponse(R2RSerializable):
    """Response for knowledge graph entities."""

    entities: list[Entity] = Field(
        ...,
        description="The list of entities in the graph.",
    )

    total_entries: int = Field(
        ...,
        description="The total number of entities in the graph for the collection or document.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entities": [
                    {
                        "id": "1",
                        "name": "Entity 1",
                        "description": "Description 1",
                    },
                    {
                        "id": "2",
                        "name": "Entity 2",
                        "description": "Description 2",
                    },
                ],
                "total_entries": 2,
            }
        }


class KGTriplesResponse(R2RSerializable):
    """Response for knowledge graph triples."""

    triples: list[Triple] = Field(
        ...,
        description="The list of triples in the graph.",
    )

    total_entries: int = Field(
        ...,
        description="The total number of triples in the graph for the collection or document.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "triples": [
                    {
                        "subject": "Paris",
                        "predicate": "is capital of",
                        "object": "France",
                        "description": "Paris is the capital of France",
                    }
                ],
                "total_entries": 2,
            }
        }


class KGCommunitiesResponse(R2RSerializable):
    """Response for knowledge graph communities."""

    communities: list[CommunityReport] = Field(
        ...,
        description="The list of communities in the graph for the collection.",
    )

    total_entries: int = Field(
        ...,
        description="The total number of communities in the graph.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_count": 1,
                "communities": [
                    {
                        "id": "1",
                        "community_number": 1,
                        "collection_ids": [
                            "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
                        ],
                        "level": 0,
                        "name": "community name",
                        "summary": "community summary",
                        "findings": ["finding1", "finding2"],
                        "rating": "8",
                        "rating_explanation": "rating explanation",
                    }
                ],
            }
        }


WrappedKGCreationResponse = ResultsWrapper[
    Union[KGCreationResponse, KGCreationEstimationResponse]
]
WrappedKGEnrichmentResponse = ResultsWrapper[
    Union[KGEnrichmentResponse, KGEnrichmentEstimationResponse]
]
WrappedKGEntitiesResponse = ResultsWrapper[KGEntitiesResponse]
WrappedKGTriplesResponse = ResultsWrapper[KGTriplesResponse]
WrappedKGCommunitiesResponse = ResultsWrapper[KGCommunitiesResponse]
