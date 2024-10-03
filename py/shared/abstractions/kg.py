from enum import Enum

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGRunType(Enum):
    """Type of KG run."""

    ESTIMATE = "estimate"
    RUN = "run"


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

    estimated_total_time_in_minutes: str = Field(
        default="NA",
        description="The estimated total time to run the graph enrichment process.",
    )

    estimated_cost_in_usd: str = Field(
        default="NA",
        description="The estimated cost to run the graph enrichment process.",
    )

    estimated_total_time_in_minutes: str = Field(
        default="NA",
        description="The estimated total time to run the graph enrichment process.",
    )

class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    run_mode: KGRunType = Field(
        default=KGRunType.ESTIMATE,  # or run
        description="Run an estimate for the full graph creation process.",
    )

    kg_triples_extraction_prompt: str = Field(
        default="graphrag_triples_extraction_few_shot",
        description="The prompt to use for knowledge graph extraction.",
    )

    force_kg_creation: bool = Field(
        default=False,
        description="Force run the KG creation step even if the graph is already created.",
    )

    entity_types: list[str] = Field(
        default=[],
        description="The types of entities to extract.",
    )

    relation_types: list[str] = Field(
        default=[],
        description="The types of relations to extract.",
    )

    extraction_merge_count: int = Field(
        default=4,
        description="The number of extractions to merge into a single KG extraction.",
    )

    max_knowledge_triples: int = Field(
        default=100,
        description="The maximum number of knowledge triples to extract from each chunk.",
    )

    max_description_input_length: int = Field(
        default=65536,
        description="The maximum length of the description for a node in the graph.",
    )

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )


class KGEnrichmentSettings(R2RSerializable):
    """Settings for knowledge graph enrichment."""

    run_mode: str = Field(
        default="estimate",  # or run
        description="Run an estimate for the full graph enrichment process.",
    )

    skip_clustering: bool = Field(
        default=False,
        description="Whether to skip leiden clustering on the graph or not.",
    )

    force_enrichment: bool = Field(
        default=False,
        description="Force run the enrichment step even if graph creation is still in progress for some documents.",
    )

    community_reports_prompt: str = Field(
        default="graphrag_community_reports_prompt",
        description="The prompt to use for knowledge graph enrichment.",
    )

    max_summary_input_length: int = Field(
        default=65536,
        description="The maximum length of the summary for a community.",
    )

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )

    leiden_params: dict = Field(
        default_factory=dict,
        description="Parameters for the Leiden algorithm.",
    )
