from pydantic import Field

from shared.shared_abstractions.llm import GenerationConfig
from shared.shared_abstractions.shared_base import R2RSerializable


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

    entity_types: list[str] = Field(
        default=[],
        description="The types of entities to extract.",
    )

    relation_types: list[str] = Field(
        default=[],
        description="The types of relations to extract.",
    )

    fragment_merge_count: int = Field(
        default=4,
        description="The number of fragments to merge into a single KG extraction.",
    )

    max_knowledge_triples: int = Field(
        default=100,
        description="The maximum number of knowledge triples to extract from each chunk.",
    )

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )


class KGEnrichmentSettings(R2RSerializable):
    """Settings for knowledge graph enrichment."""

    max_description_input_length: int = Field(
        default=65536,
        description="The maximum length of the description for a node in the graph.",
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
