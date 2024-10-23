# Abstractions for ingestion

from enum import Enum

from pydantic import Field

from .base import R2RSerializable
from .llm import GenerationConfig


class ChunkEnrichmentStrategy(str, Enum):
    SEMANTIC = "semantic"
    NEIGHBORHOOD = "neighborhood"

    def __str__(self) -> str:
        return self.value


class ChunkEnrichmentSettings(R2RSerializable):
    """
    Settings for chunk enrichment.
    """

    enable_chunk_enrichment: bool = Field(
        default=False,
        description="Whether to enable chunk enrichment or not",
    )
    strategies: list[ChunkEnrichmentStrategy] = Field(
        default=[],
        description="The strategies to use for chunk enrichment. Union of chunks obtained from each strategy is used as context.",
    )
    forward_chunks: int = Field(
        default=3,
        description="The number after the current chunk to include in the LLM context while enriching",
    )
    backward_chunks: int = Field(
        default=3,
        description="The number of chunks before the current chunk in the LLM context while enriching",
    )
    semantic_neighbors: int = Field(
        default=10, description="The number of semantic neighbors to include"
    )
    semantic_similarity_threshold: float = Field(
        default=0.7,
        description="The similarity threshold for semantic neighbors",
    )
    generation_config: GenerationConfig = Field(
        default=GenerationConfig(),
        description="The generation config to use for chunk enrichment",
    )
