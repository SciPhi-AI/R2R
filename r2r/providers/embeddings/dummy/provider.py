import logging
import random

from r2r.core import EmbeddingConfig, EmbeddingProvider, SearchResult

logger = logging.getLogger(__name__)


class DummyEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: EmbeddingConfig):
        logger.info(
            "Initializing `DummyEmbeddingProvider` to provide embeddings."
        )
        super().__init__(config)
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize SentenceTransformerEmbeddingProvider."
            )

        self.base_dimension = config.base_dimension

        if not self.base_dimension:
            raise ValueError(
                "Must set base_dimension in order to initialize DummyEmbeddingProvider."
            )

        if config.rerank_model:
            raise ValueError(
                "DummyEmbeddingProvider does not support separate reranking."
            )

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "DummyEmbeddingProvider only supports search stage."
            )
        return [random.random() for _ in range(self.base_dimension)]

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "DummyEmbeddingProvider only supports search stage."
            )

        return [
            [random.random() for _ in range(self.base_dimension)]
            for text in texts
        ]

    # TODO: This should be the default (base class) implementation instead of 'pass'.
    def rerank(
        self,
        transformed_query: str,
        texts: list[SearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ):
        return texts[:limit]

    def tokenize_string(
        self,
        text: str,
        model: str,
        stage: EmbeddingProvider.PipeStage,
    ) -> list[int]:
        """Tokenizes the input string."""
        return [0]
