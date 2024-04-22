from abc import ABC, abstractmethod
from enum import Enum

from ..providers.vector_db import VectorSearchResult


class EmbeddingProvider(ABC):
    """An abstract class to provide a common interface for embedding providers."""

    class PipelineStage(Enum):
        SEARCH = 1
        RERANK = 2

    supported_providers = ["openai", "sentence-transformers"]

    def __init__(self, config: dict):
        self.config = config
        provider = config.get("provider", None)
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize EmbeddingProvider."
            )
        if provider not in EmbeddingProvider.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in EmbeddingProvider's list of supported providers."
            )

    @abstractmethod
    def get_embedding(
        self, text: str, stage: PipelineStage = PipelineStage.SEARCH
    ):
        pass

    @abstractmethod
    def get_embeddings(
        self, texts: list[str], stage: PipelineStage = PipelineStage.SEARCH
    ):
        pass

    def rerank(
        self,
        query: str,
        documents: list[VectorSearchResult],
        stage: PipelineStage = PipelineStage.RERANK,
        limit: int = 10,
    ):
        return documents

    @abstractmethod
    def tokenize_string(
        self, text: str, model: str, stage: PipelineStage
    ) -> list[int]:
        """Tokenizes the input string."""
        pass
