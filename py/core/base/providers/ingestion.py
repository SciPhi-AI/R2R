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

    audio_transcription_model: str = "openai/whisper-1"

    vision_img_prompt_name: str = "vision_img"
    vision_img_model: str = "openai/gpt-4-mini"

    vision_pdf_prompt_name: str = "vision_pdf"
    vision_pdf_model: str = "openai/gpt-4-mini"

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
