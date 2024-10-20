import logging
from abc import ABC
from enum import Enum

from shared.abstractions.ingestion import ChunkEnrichmentSettings

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class IngestionConfig(ProviderConfig):
    provider: str = "r2r"
    excluded_parsers: list[str] = ["mp4"]
    chunk_enrichment_settings: ChunkEnrichmentSettings = (
        ChunkEnrichmentSettings()
    )
    extra_parsers: dict[str, str] = {}

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api"]

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")


class IngestionProvider(Provider, ABC):
    pass


class ChunkingStrategy(str, Enum):
    RECURSIVE = "recursive"
    CHARACTER = "character"
    BASIC = "basic"
    BY_TITLE = "by_title"
