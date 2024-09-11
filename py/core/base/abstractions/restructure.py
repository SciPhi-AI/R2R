from uuid import UUID

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

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

    generation_config: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )

    leiden_params: dict = Field(
        default_factory=dict,
        description="Parameters for the Leiden algorithm.",
    )
