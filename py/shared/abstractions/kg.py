from enum import Enum

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGRunType(str, Enum):
    """Type of KG run."""

    ESTIMATE = "estimate"
    RUN = "run"

    def __str__(self):
        return self.value


class KGEntityDeduplicationType(str, Enum):
    """Type of KG entity deduplication."""

    BY_NAME = "by_name"
    BY_DESCRIPTION = "by_description"

    def __str__(self):
        return self.value


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    graphrag_triples_extraction_few_shot: str = Field(
        default="graphrag_triples_extraction_few_shot",
        description="The prompt to use for knowledge graph extraction.",
        alias="graphrag_triples_extraction_few_shot_prompt",  # TODO - mark deprecated & remove
    )

    graphrag_entity_description: str = Field(
        default="graphrag_entity_description",
        description="The prompt to use for entity description generation.",
        alias="graphrag_entity_description_prompt",  # TODO - mark deprecated & remove
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


class KGEntityDeduplicationSettings(R2RSerializable):
    """Settings for knowledge graph entity deduplication."""

    kg_entity_deduplication_type: KGEntityDeduplicationType = Field(
        default=KGEntityDeduplicationType.BY_NAME,
        description="The type of entity deduplication to use.",
    )

    max_description_input_length: int = Field(
        default=65536,
        description="The maximum length of the description for a node in the graph.",
    )

    kg_entity_deduplication_prompt: str = Field(
        default="graphrag_entity_deduplication",
        description="The prompt to use for knowledge graph entity deduplication.",
    )

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph entity deduplication.",
    )


class KGEnrichmentSettings(R2RSerializable):
    """Settings for knowledge graph enrichment."""

    force_kg_enrichment: bool = Field(
        default=False,
        description="Force run the enrichment step even if graph creation is still in progress for some documents.",
    )

    graphrag_community_reports: str = Field(
        default="graphrag_community_reports",
        description="The prompt to use for knowledge graph enrichment.",
        alias="graphrag_community_reports",  # TODO - mark deprecated & remove
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
