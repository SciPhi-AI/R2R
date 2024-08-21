from typing import Optional
from pydantic import BaseModel, Field

from .llm import GenerationConfig


class KGEnrichmentSettings(BaseModel):
    """Settings for knowledge graph enrichment."""

    generation_config: GenerationConfig = Field(default_factory=GenerationConfig, description="Configuration for text generation during graph enrichment.")
    leiden_params: dict = Field(default_factory=dict, description="Parameters for the Leiden algorithm.")