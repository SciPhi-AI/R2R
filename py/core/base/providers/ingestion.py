import logging
from abc import ABC
from enum import Enum

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class IngestionConfig(ProviderConfig):
    provider: str = "r2r"
    excluded_parsers: list[str] = ["mp4"]

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
