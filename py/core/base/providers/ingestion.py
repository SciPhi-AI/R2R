import logging
from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from pydantic import Field

from core.base.abstractions import ChunkEnrichmentSettings

from .base import AppConfig, Provider, ProviderConfig
from .llm import CompletionProvider

logger = logging.getLogger()

if TYPE_CHECKING:
    from core.providers.database import PostgresDatabaseProvider


class ChunkingStrategy(str, Enum):
    RECURSIVE = "recursive"
    CHARACTER = "character"
    BASIC = "basic"
    BY_TITLE = "by_title"


class IngestionMode(str, Enum):
    hi_res = "hi-res"
    fast = "fast"
    custom = "custom"


class IngestionConfig(ProviderConfig):
    _defaults: ClassVar[dict] = {
        "app": AppConfig(),
        "provider": "r2r",
        "excluded_parsers": ["mp4"],
        "chunking_strategy": "recursive",
        "chunk_size": 1024,
        "chunk_enrichment_settings": ChunkEnrichmentSettings(),
        "extra_parsers": {},
        "audio_transcription_model": None,
        "vision_img_prompt_name": "vision_img",
        "vision_img_model": None,
        "vision_pdf_prompt_name": "vision_pdf",
        "vision_pdf_model": None,
        "skip_document_summary": False,
        "document_summary_system_prompt": "system",
        "document_summary_task_prompt": "summary",
        "document_summary_max_length": 100_000,
        "chunks_for_document_summary": 128,
        "document_summary_model": None,
        "parser_overrides": {},
        "extra_fields": {},
        "automatic_extraction": False,
    }

    provider: str = Field(
        default_factory=lambda: IngestionConfig._defaults["provider"]
    )
    excluded_parsers: list[str] = Field(
        default_factory=lambda: IngestionConfig._defaults["excluded_parsers"]
    )
    chunking_strategy: str | ChunkingStrategy = Field(
        default_factory=lambda: IngestionConfig._defaults["chunking_strategy"]
    )
    chunk_size: int = Field(
        default_factory=lambda: IngestionConfig._defaults["chunk_size"]
    )
    chunk_enrichment_settings: ChunkEnrichmentSettings = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "chunk_enrichment_settings"
        ]
    )
    extra_parsers: dict[str, Any] = Field(
        default_factory=lambda: IngestionConfig._defaults["extra_parsers"]
    )
    audio_transcription_model: Optional[str] = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "audio_transcription_model"
        ]
    )
    vision_img_prompt_name: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "vision_img_prompt_name"
        ]
    )
    vision_img_model: Optional[str] = Field(
        default_factory=lambda: IngestionConfig._defaults["vision_img_model"]
    )
    vision_pdf_prompt_name: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "vision_pdf_prompt_name"
        ]
    )
    vision_pdf_model: Optional[str] = Field(
        default_factory=lambda: IngestionConfig._defaults["vision_pdf_model"]
    )
    skip_document_summary: bool = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "skip_document_summary"
        ]
    )
    document_summary_system_prompt: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "document_summary_system_prompt"
        ]
    )
    document_summary_task_prompt: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "document_summary_task_prompt"
        ]
    )
    chunks_for_document_summary: int = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "chunks_for_document_summary"
        ]
    )
    document_summary_model: Optional[str] = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "document_summary_model"
        ]
    )
    parser_overrides: dict[str, str] = Field(
        default_factory=lambda: IngestionConfig._defaults["parser_overrides"]
    )
    automatic_extraction: bool = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "automatic_extraction"
        ]
    )
    document_summary_max_length: int = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "document_summary_max_length"
        ]
    )

    @classmethod
    def set_default(cls, **kwargs):
        for key, value in kwargs.items():
            if key in cls._defaults:
                cls._defaults[key] = value
            else:
                raise AttributeError(
                    f"No default attribute '{key}' in IngestionConfig"
                )

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
            return cls(app=app, parser_overrides={"pdf": "zerox"})
        if mode == "fast":
            return cls(app=app, skip_document_summary=True)
        else:
            return cls(app=app)


class IngestionProvider(Provider, ABC):
    config: IngestionConfig
    database_provider: "PostgresDatabaseProvider"
    llm_provider: CompletionProvider

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: "PostgresDatabaseProvider",
        llm_provider: CompletionProvider,
    ):
        super().__init__(config)
        self.config: IngestionConfig = config
        self.llm_provider = llm_provider
        self.database_provider: "PostgresDatabaseProvider" = database_provider
