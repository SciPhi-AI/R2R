import logging
import os
from typing import Any, List

from ollama import AsyncClient, Client

from core.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    R2RException,
    VectorSearchResult,
)

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
        self.base_url = os.getenv("OLLAMA_API_BASE")
        logger.info(
            f"Using Ollama API base URL: {self.base_url or 'http://127.0.0.1:11434'}"
        )
        self.client = Client(host=self.base_url)
        self.aclient = AsyncClient(host=self.base_url)

        self.set_prefixes(config.prefixes or {}, self.base_model)
        self.batch_size = config.batch_size or 32

    def _get_embedding_kwargs(self, **kwargs):
        embedding_kwargs = {
            "model": self.base_model,
        }
        embedding_kwargs.update(kwargs)
        return embedding_kwargs

    async def _execute_task(self, task: dict[str, Any]) -> List[List[float]]:
        texts = task["texts"]
        purpose = task.get("purpose", EmbeddingPurpose.INDEX)
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        try:
            embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                prefixed_batch = [
                    self.prefixes.get(purpose, "") + text for text in batch
                ]
                response = await self.aclient.embed(
                    input=prefixed_batch, **kwargs
                )
                embeddings.extend(response["embeddings"])
            return embeddings
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise R2RException(error_msg, 400)

    def _execute_task_sync(self, task: dict[str, Any]) -> List[List[float]]:
        texts = task["texts"]
        purpose = task.get("purpose", EmbeddingPurpose.INDEX)
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        try:
            embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                prefixed_batch = [
                    self.prefixes.get(purpose, "") + text for text in batch
                ]
                response = self.client.embed(input=prefixed_batch, **kwargs)
                embeddings.extend(response["embeddings"])
            return embeddings
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
                "OllamaEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        result = await self._execute_with_backoff_async(task)
        return result[0]

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )

        task = {
            "texts": [text],
            "stage": stage,
            "purpose": purpose,
            "kwargs": kwargs,
        }
        result = self._execute_with_backoff_sync(task)
        return result[0]

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[List[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
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
                "OllamaEmbeddingProvider only supports search stage."
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
    ) -> list[VectorSearchResult]:
        return results[:limit]
