import logging
import os
from typing import Any

import litellm
from litellm import AuthenticationError, aembedding, embedding

from core.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    R2RException,
    VectorSearchResult,
)

logger = logging.getLogger()


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(config)

        # Allow LiteLLM to automatically drop parameters that are not supported by the model
        litellm.drop_params = True

        self.litellm_embedding = embedding
        self.litellm_aembedding = aembedding

        if not config.provider:
            raise ValueError(
                "Must set provider in order to initialize `LiteLLMEmbeddingProvider`."
            )
        if config.provider != "litellm":
            raise ValueError(
                "LiteLLMEmbeddingProvider must be initialized with provider `litellm`."
            )
        if config.rerank_model:
            raise ValueError(
                "LiteLLMEmbeddingProvider does not support separate reranking."
            )

        self.base_model = config.base_model
        self.base_dimension = config.base_dimension
        self.api_base = os.getenv("API_BASE")
        if self.api_base:
            logger.info(f"Using API base: {self.api_base}")

    def _get_embedding_kwargs(self, **kwargs):
        return {
            "model": self.base_model,
            "api_base": self.api_base,
        } | kwargs

    async def _execute_task(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        try:
            response = await self.litellm_aembedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except AuthenticationError as e:
            logger.error(
                "Authentication error: Invalid API key or credentials."
            )
            raise
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)

            raise R2RException(error_msg, 400)

    def _execute_task_sync(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            response = self.litellm_embedding(
                input=texts,
                **kwargs,
            )
            return [data["embedding"] for data in response.data]
        except AuthenticationError as e:
            logger.error(
                "Authentication error: Invalid API key or credentials."
            )
            raise
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
    ) -> list[float]:
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
    ) -> list[float]:
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
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
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
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
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
