import logging
from abc import ABC
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from core.base.abstractions import ChunkEnrichmentSettings

from .base import AppConfig, Provider, ProviderConfig
from .database import DatabaseProvider
from .llm import CompletionProvider

logger = logging.getLogger()


class IngestionConfig(ProviderConfig):
    _defaults: ClassVar[dict] = {
        "app": AppConfig(),
        "provider": "r2r",
        "excluded_parsers": ["mp4"],
        "chunk_enrichment_settings": ChunkEnrichmentSettings(),
        "extra_parsers": {},
        "audio_transcription_model": "openai/whisper-1",
        "vision_img_prompt_name": "vision_img",
        "vision_img_model": "openai/gpt-4o",
        "vision_pdf_prompt_name": "vision_pdf",
        "vision_pdf_model": "openai/gpt-4o",
        "skip_document_summary": False,
        "document_summary_system_prompt": "default_system",
        "document_summary_task_prompt": "default_summary",
        "chunks_for_document_summary": 128,
        "document_summary_model": "openai/gpt-4o-mini",
        "parser_overrides": {},
        "extra_fields": {},
    }

    provider: str = Field(
        default_factory=lambda: IngestionConfig._defaults["provider"]
    )
    excluded_parsers: list[str] = Field(
        default_factory=lambda: IngestionConfig._defaults["excluded_parsers"]
    )
    chunk_enrichment_settings: ChunkEnrichmentSettings = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "chunk_enrichment_settings"
        ]
    )
    extra_parsers: dict[str, str] = Field(
        default_factory=lambda: IngestionConfig._defaults["extra_parsers"]
    )
    audio_transcription_model: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "audio_transcription_model"
        ]
    )
    vision_img_prompt_name: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "vision_img_prompt_name"
        ]
    )
    vision_img_model: str = Field(
        default_factory=lambda: IngestionConfig._defaults["vision_img_model"]
    )
    vision_pdf_prompt_name: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "vision_pdf_prompt_name"
        ]
    )
    vision_pdf_model: str = Field(
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
    document_summary_model: str = Field(
        default_factory=lambda: IngestionConfig._defaults[
            "document_summary_model"
        ]
    )
    parser_overrides: dict[str, str] = Field(
        default_factory=lambda: IngestionConfig._defaults["parser_overrides"]
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
        else:
            return cls(app=app)

    @classmethod
    def get_default(cls, mode: str, app) -> "IngestionConfig":
        """Return default ingestion configuration for a given mode."""
        if mode == "hi-res":
            # More thorough parsing, no skipping summaries, possibly larger `chunks_for_document_summary`.
            return cls(app=app, parser_overrides={"pdf": "zerox"})
        # elif mode == "fast":
        #     # Skip summaries and other enrichment steps for speed.
        #     return cls(
        #         app=app,
        #     )
        else:
            # For `custom` or any unrecognized mode, return a base config
            return cls(app=app)

    @classmethod
    def set_default(cls, **kwargs):
        for key, value in kwargs.items():
            if key in cls._defaults:
                cls._defaults[key] = value
            else:
                raise AttributeError(
                    f"No default attribute '{key}' in GenerationConfig"
                )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "provider": "r2r",
            "excluded_parsers": ["mp4"],
            "chunk_enrichment_settings": ChunkEnrichmentSettings().dict(),
            "extra_parsers": {},
            "audio_transcription_model": "openai/whisper-1",
            "vision_img_prompt_name": "vision_img",
            "vision_img_model": "openai/gpt-4o",
            "vision_pdf_prompt_name": "vision_pdf",
            "vision_pdf_model": "openai/gpt-4o",
            "skip_document_summary": False,
            "document_summary_system_prompt": "default_system",
            "document_summary_task_prompt": "default_summary",
            "chunks_for_document_summary": 128,
            "document_summary_model": "openai/gpt-4o-mini",
            "parser_overrides": {},
        }


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
