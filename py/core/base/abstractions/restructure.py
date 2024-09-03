from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig
from uuid import UUID


class KGEnrichmentSettings(R2RSerializable):
    """Settings for knowledge graph enrichment."""

    max_knowledge_triples: int = Field(
        default=100,
        description="The maximum number of knowledge triples to extract from each chunk.",
    )

    document_ids: list[UUID] = Field(
        default_factory=list,
        description="The document IDs to enrich.",
    )

    generation_config_triplet: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )

    generation_config_enrichment: GenerationConfig = Field(
        default_factory=GenerationConfig,
        description="Configuration for text generation during graph enrichment.",
    )

    leiden_params: dict = Field(
        default_factory=dict,
        description="Parameters for the Leiden algorithm.",
    )
