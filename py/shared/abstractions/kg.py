from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    clustering_mode: str = Field(
        default="local",
        description="Whether to use remote clustering for graph creation.",
    )

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
        default=2,
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

    automatic_deduplication: bool = Field(
        default=False,
        description="Whether to automatically deduplicate entities.",
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
