import logging
from abc import abstractmethod
from enum import Enum
from typing import Optional

from ..abstractions.embedding import (
    EmbeddingPurpose,
    default_embedding_prefixes,
)
from ..abstractions.search import VectorSearchResult
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class EmbeddingConfig(ProviderConfig):
    """A base embedding configuration class"""

    provider: Optional[str] = None
    base_model: Optional[str] = None
    base_dimension: Optional[int] = None
    rerank_model: Optional[str] = None
    rerank_dimension: Optional[int] = None
    rerank_transformer_type: Optional[str] = None
    batch_size: int = 1
    prefixes: Optional[dict[str, str]] = None
    add_title_as_prefix: bool = True

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return [None, "litellm", "openai", "ollama", "sentence-transformers"]


class EmbeddingProvider(Provider):
    """An abstract class to provide a common interface for embedding providers."""

    class PipeStage(Enum):
        BASE = 1
        RERANK = 2

    def __init__(self, config: EmbeddingConfig):
        if not isinstance(config, EmbeddingConfig):
            raise ValueError(
                "EmbeddingProvider must be initialized with a `EmbeddingConfig`."
            )
        logger.info(f"Initializing EmbeddingProvider with config {config}.")

        super().__init__(config)

    @abstractmethod
    def get_embedding(
        self,
        text: str,
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        pass

    async def async_get_embedding(
        self,
        text: str,
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        return self.get_embedding(text, stage, purpose)

    @abstractmethod
    def get_embeddings(
        self,
        texts: list[str],
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        pass

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        return self.get_embeddings(texts, stage, purpose)

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: PipeStage = PipeStage.RERANK,
        limit: int = 10,
    ):
        pass

    @abstractmethod
    def tokenize_string(
        self, text: str, model: str, stage: PipeStage
    ) -> list[int]:
        """Tokenizes the input string."""
        pass

    def set_prefixes(self, config_prefixes: dict[str, str], base_model: str):
        self.prefixes = {}

        # use the configured prefixes if given
        for t, p in config_prefixes.items():
            purpose = EmbeddingPurpose(t.lower())
            self.prefixes[purpose] = p

        # but apply known defaults otherwise
        if base_model in default_embedding_prefixes:
            for t, p in default_embedding_prefixes[base_model].items():
                if t not in self.prefixes:
                    self.prefixes[t] = p
