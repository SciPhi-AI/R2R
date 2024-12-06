import logging
from abc import ABC
from enum import Enum

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

    audio_transcription_model: str = "openai/whisper-1"

    vision_img_prompt_name: str = "vision_img"
    vision_img_model: str = "openai/gpt-4o"

    vision_pdf_prompt_name: str = "vision_pdf"
    vision_pdf_model: str = "openai/gpt-4o"

    skip_document_summary: bool = False
    document_summary_system_prompt: str = "default_system"
    document_summary_task_prompt: str = "default_summary"
    chunks_for_document_summary: int = 128
    document_summary_model: str = "openai/gpt-4o-mini"

    parser_overrides: dict[str, str] = {}

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r", "unstructured_local", "unstructured_api"]

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")


    @classmethod
    def get_default(cls, mode: str, app) -> "IngestionConfig":
        """Return default ingestion configuration for a given mode."""
        if mode == "hi-res":
            # More thorough parsing, no skipping summaries, possibly larger `chunks_for_document_summary`.
            return cls(
                app=app,
                parser_overrides={
                    "pdf": "zerox"
                }
            )
        # elif mode == "fast":
        #     # Skip summaries and other enrichment steps for speed.
        #     return cls(
        #         app=app,
        #     )
        else:
            # For `custom` or any unrecognized mode, return a base config
            return cls(
                app=app
            )

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

class IngestionMode(str, Enum):
    hi_res = "hi-res"
    fast = "fast"
    custom = "custom"
