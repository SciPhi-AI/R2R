from uuid import UUID

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class KGCreationSettings(R2RSerializable):
    """Settings for knowledge graph creation."""

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
