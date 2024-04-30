from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .base import Provider, ProviderConfig
from .vector_db import VectorSearchResult


@dataclass
class EmbeddingConfig(ProviderConfig):
    """A base embedding configuration class"""

    provider: Optional[str] = None
    search_model: Optional[str] = None
    search_dimension: Optional[int] = None
    rerank_model: Optional[str] = None

    def validate(self) -> None:
        if not self.provider:
            raise ValueError(
                "The 'provider' field must be set for EmbeddingConfig."
            )
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> List[str]:
        return ["dummy", "openai", "sentence-transformers"]


class EmbeddingProvider(Provider):
    """An abstract class to provide a common interface for embedding providers."""

    class PipelineStage(Enum):
        SEARCH = 1
        RERANK = 2

    def __init__(self, config: EmbeddingConfig):
        if not isinstance(config, EmbeddingConfig):
            raise ValueError(
                "EmbeddingProvider must be initialized with a `EmbeddingConfig`."
            )

        super().__init__(config)

    @abstractmethod
    def get_embedding(
        self, text: str, stage: PipelineStage = PipelineStage.SEARCH
    ):
        pass

    async def async_get_embedding(self, text: str, stage: PipelineStage = PipelineStage.SEARCH):
        return self.get_embedding(text, stage)

    @abstractmethod
    def get_embeddings(
        self, texts: list[str], stage: PipelineStage = PipelineStage.SEARCH
    ):
        pass

    async def async_get_embeddings(self, texts: list[str], stage: PipelineStage = PipelineStage.SEARCH):
        return self.get_embeddings(texts, stage)

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[VectorSearchResult],
        stage: PipelineStage = PipelineStage.RERANK,
        limit: int = 10,
    ):
        pass

    @abstractmethod
    def tokenize_string(
        self, text: str, model: str, stage: PipelineStage
    ) -> list[int]:
        """Tokenizes the input string."""
        pass
