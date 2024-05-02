import logging
import random

from r2r.core import EmbeddingProvider, VectorSearchResult

logger = logging.getLogger(__name__)


class DummyEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: dict):
        logger.info(
            "Initializing `DummyEmbeddingProvider` to provide embeddings."
        )
        super().__init__(config)
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize SentenceTransformerEmbeddingProvider."
            )

        self.search_dimension = config.search_dimension

        if not self.search_dimension:
            raise ValueError(
                "Must set search_dimension in order to initialize DummyEmbeddingProvider."
            )

        if config.rerank_model:
            raise ValueError(
                "DummyEmbeddingProvider does not support separate reranking."
            )

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipelineStage = EmbeddingProvider.PipelineStage.SEARCH,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipelineStage.SEARCH:
            raise ValueError(
                "DummyEmbeddingProvider only supports search stage."
            )
        return [random.random() for _ in range(self.search_dimension)]

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipelineStage = EmbeddingProvider.PipelineStage.SEARCH,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipelineStage.SEARCH:
            raise ValueError(
                "DummyEmbeddingProvider only supports search stage."
            )

        return [
            [random.random() for _ in range(self.search_dimension)]
            for text in texts
        ]

    # TODO: This should be the default (base class) implementation instead of 'pass'.
    def rerank(
        self,
        transformed_query: str,
        texts: list[VectorSearchResult],
        stage: EmbeddingProvider.PipelineStage = EmbeddingProvider.PipelineStage.RERANK,
        limit: int = 10,
    ):
        return texts[:limit]

    def tokenize_string(
        self,
        text: str,
        model: str,
        stage: EmbeddingProvider.PipelineStage,
    ) -> list[int]:
        """Tokenizes the input string."""
        return [0]
