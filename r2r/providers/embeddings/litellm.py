import asyncio
import logging

from litellm import aembedding, embedding

from r2r.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
        *args,
        **kwargs,
    ) -> None:

        self.litellm_embedding = embedding
        self.litellm_aembedding = aembedding
        super().__init__(config)

        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize `LiteLLMEmbeddingProvider`."
            )
        if provider != "litellm":
            raise ValueError(
                "LiteLLMEmbeddingProvider must be initialized with provider `litellm`."
            )
        if config.rerank_model:
            raise ValueError(
                "LiteLLMEmbeddingProvider does not support separate reranking."
            )

        self.base_model = config.base_model
        self.base_dimension = config.base_dimension

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        try:
            return self.litellm_embedding(
                model=self.base_model,
                input=text,
                **kwargs,
            ).data[0]["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        return [
            self.litellm_embedding(
                model=self.base_model, input=text, **kwargs
            ).data[0]["embedding"]
            for text in texts
        ]

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        try:
            response = await self.litellm_aembedding(
                model=self.base_model,
                input=text,
                **kwargs,
            )
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )
        try:
            responses = await asyncio.gather(
                *[
                    self.litellm_aembedding(
                        model=self.base_model,
                        input=text,
                        **kwargs,
                    )
                    for text in texts
                ]
            )
            return [response.data[0]["embedding"] for response in responses]
        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}")
            raise

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
        raise NotImplementedError(
            "Tokenization is not supported by LiteLLMEmbeddingProvider."
        )
