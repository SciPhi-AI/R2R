from enum import Enum

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGRunType(str, Enum):
    """Type of KG run."""

    ESTIMATE = "estimate"
    RUN = "run"


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

    force_kg_enrichment: bool = Field(
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
