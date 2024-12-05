from enum import Enum

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGRunType(str, Enum):
    """Type of KG run."""

    ESTIMATE = "estimate"
    RUN = "run"  # deprecated

    def __str__(self):
        return self.value


GraphRunType = KGRunType


class KGEntityDeduplicationType(str, Enum):
    """Type of KG entity deduplication."""

    BY_NAME = "by_name"
    BY_DESCRIPTION = "by_description"
    BY_LLM = "by_llm"

    def __str__(self):
        return self.value


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    graphrag_relationships_extraction_few_shot: str = Field(
        default="graphrag_relationships_extraction_few_shot",
        description="The prompt to use for knowledge graph extraction.",
        alias="graphrag_relationships_extraction_few_shot",  # TODO - mark deprecated & remove
    )

    graph_entity_description_prompt: str = Field(
        default="graphrag_entity_description",
        description="The prompt to use for entity description generation.",
        alias="graphrag_entity_description_prompt",  # TODO - mark deprecated & remove
    )

    entity_types: list[str] = Field(
        default=[],
        description="The types of entities to extract.",
    )

    relation_types: list[str] = Field(
        default=[],
        description="The types of relations to extract.",
    )

    chunk_merge_count: int = Field(
        default=4,
        description="The number of extractions to merge into a single KG extraction.",
    )

    max_knowledge_relationships: int = Field(
        default=100,
        description="The maximum number of knowledge relationships to extract from each chunk.",
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

    graph_entity_deduplication_type: KGEntityDeduplicationType = Field(
        default=KGEntityDeduplicationType.BY_NAME,
        description="The type of entity deduplication to use.",
    )

    max_description_input_length: int = Field(
        default=65536,
        description="The maximum length of the description for a node in the graph.",
    )

    graph_entity_deduplication_prompt: str = Field(
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

    graphrag_communities: str = Field(
        default="graphrag_communities",
        description="The prompt to use for knowledge graph enrichment.",
        alias="graphrag_communities",  # TODO - mark deprecated & remove
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


class GraphEntitySettings(R2RSerializable):
    """Settings for knowledge graph entity creation."""

    graph_entity_deduplication_type: KGEntityDeduplicationType = Field(
        default=KGEntityDeduplicationType.BY_NAME,
        description="The type of entity deduplication to use.",
    )

    max_description_input_length: int = Field(
        default=65536,
        description="The maximum length of the description for a node in the graph.",
    )

    graph_entity_deduplication_prompt: str = Field(
        default="graphrag_entity_deduplication",
        description="The prompt to use for knowledge graph entity deduplication.",
    )

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph entity deduplication.",
    )


class GraphRelationshipSettings(R2RSerializable):
    """Settings for knowledge graph relationship creation."""

    pass


class GraphCommunitySettings(R2RSerializable):
    """Settings for knowledge graph community enrichment."""

    force_kg_enrichment: bool = Field(
        default=False,
        description="Force run the enrichment step even if graph creation is still in progress for some documents.",
    )

    graphrag_communities: str = Field(
        default="graphrag_communities",
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


class GraphBuildSettings(R2RSerializable):
    """Settings for knowledge graph build."""

    entity_settings: GraphEntitySettings = Field(
        default=GraphEntitySettings(),
        description="Settings for knowledge graph entity creation.",
    )

    relationship_settings: GraphRelationshipSettings = Field(
        default=GraphRelationshipSettings(),
        description="Settings for knowledge graph relationship creation.",
    )

    community_settings: GraphCommunitySettings = Field(
        default=GraphCommunitySettings(),
        description="Settings for knowledge graph community enrichment.",
    )
