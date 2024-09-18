import logging
from typing import Any, List

import litellm
from litellm import aembedding, embedding

from core.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    R2RException,
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
        super().__init__(config)

        self.litellm_embedding = embedding
        self.litellm_aembedding = aembedding

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
        if "amazon" in self.base_model:
            logger.warn("Amazon embedding model detected, dropping params")
            litellm.drop_params = True
        self.base_dimension = config.base_dimension

    def _get_embedding_kwargs(self, **kwargs):
        embedding_kwargs = {
            "model": self.base_model,
            "dimensions": self.base_dimension,
        }
        embedding_kwargs.update(kwargs)
        return embedding_kwargs

    async def _execute_task(self, task: dict[str, Any]) -> List[List[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        try:
            response = await self.litellm_aembedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)

            raise R2RException(error_msg, 400)

    def _execute_task_sync(self, task: dict[str, Any]) -> List[List[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            response = self.litellm_embedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise R2RException(error_msg, 400)

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return (await self._execute_with_backoff_async(task))[0]

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "Error getting embeddings: LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return self._execute_with_backoff_sync(task)[0]

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[List[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return await self._execute_with_backoff_async(task)

    def get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[List[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "LiteLLMEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return self._execute_with_backoff_sync(task)

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
