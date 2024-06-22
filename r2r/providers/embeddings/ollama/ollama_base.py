import logging

import ollama
from ollama import AsyncClient

from r2r.core import EmbeddingConfig, EmbeddingProvider, VectorSearchResult

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize `OllamaEmbeddingProvider`."
            )

        if provider != "ollama":
            raise ValueError(
                "OllamaEmbeddingProvider must be initialized with provider `ollama`."
            )

        if config.rerank_model:
            raise ValueError(
                "OllamaEmbeddingProvider does not support separate reranking."
            )
        self.base_model = config.base_model
        self.base_dimension = config.base_dimension

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )

        response = ollama.embeddings(prompt=text, model=self.base_model)
        return response["embedding"]

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        response = await AsyncClient().embeddings(
            prompt=text, model=self.base_model
        )
        return response["embedding"]

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        for text in texts:
            yield self.get_embedding(text, stage)

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        import asyncio

        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )
        # Use asyncio.gather to run all embedding tasks concurrently
        responses = await asyncio.gather(
            *[self.async_get_embedding(text, stage) for text in texts]
        )
        return responses

    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ):
        return results[:limit]

    def tokenize_string(
        self, text: str, model: str, stage: EmbeddingProvider.PipeStage
    ) -> list[int]:
        """Tokenizes the input string."""
        raise NotImplementedError(
            "Tokenization is not supported by OllamaEmbeddingProvider."
        )
