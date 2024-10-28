import logging
from abc import ABC
from enum import Enum
from typing import Optional

from core.base.abstractions import ChunkEnrichmentSettings

from .base import Provider, ProviderConfig
from .database import DatabaseProvider
from .llm import CompletionProvider

logger = logging.getLogger()


class IngestionConfig(ProviderConfig):
    provider: str = "r2r"
    excluded_parsers: list[str] = ["mp4"]
    chunk_enrichment_settings: ChunkEnrichmentSettings = (
        ChunkEnrichmentSettings()
    )
    extra_parsers: dict[str, str] = {}

    audio_transcription_model: str

    vision_prompt: Optional[str] = None
    vision_model: str

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api"]

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")


class IngestionProvider(Provider, ABC):

    config: IngestionConfig
    database_provider: DatabaseProvider
    llm_provider: CompletionProvider

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        super().__init__(config)
        self.config: IngestionConfig = config
        self.llm_provider = llm_provider
        self.database_provider = database_provider


class ChunkingStrategy(str, Enum):
    RECURSIVE = "recursive"
    CHARACTER = "character"
    BASIC = "basic"
    BY_TITLE = "by_title"
