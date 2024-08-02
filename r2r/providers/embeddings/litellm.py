import asyncio
import logging
from typing import Any, List

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
        self.base_dimension = config.base_dimension
        self.semaphore = asyncio.Semaphore(config.concurrent_request_limit)

    def _get_embedding_kwargs(self, **kwargs):
        embedding_kwargs = {
            "model": self.base_model,
            "dimensions": self.base_dimension,
        }
        embedding_kwargs.update(kwargs)
        return embedding_kwargs

    async def _execute_task(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            response = await self.litellm_aembedding(
                input=[text],
                **kwargs,
            )
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

    def _execute_task_sync(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            return self.litellm_embedding(
                input=[text],
                **kwargs,
            ).data[
                0
            ]["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

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
            "text": text,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return await self._execute_with_backoff_async(task)

    def get_embedding(
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
            "text": text,
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        return self._execute_with_backoff_sync(task)

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

        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
                "kwargs": kwargs,
            }
            for text in texts
        ]
        return await asyncio.gather(
            *[self._execute_with_backoff_async(task) for task in tasks]
        )

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

        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
                "kwargs": kwargs,
            }
            for text in texts
        ]
        return [self._execute_with_backoff_sync(task) for task in tasks]

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
