import logging
import os
from typing import Any

import tiktoken
from openai import AsyncOpenAI, AuthenticationError, OpenAI
from openai._types import NOT_GIVEN

from core.base import (
    ChunkSearchResult,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
)

logger = logging.getLogger()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    MODEL_TO_TOKENIZER = {
        "text-embedding-ada-002": "cl100k_base",
        "text-embedding-3-small": "cl100k_base",
        "text-embedding-3-large": "cl100k_base",
    }
    MODEL_TO_DIMENSIONS = {
        "text-embedding-ada-002": [1536],
        "text-embedding-3-small": [512, 1536],
        "text-embedding-3-large": [256, 1024, 3072],
    }

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        if not config.provider:
            raise ValueError(
                "Must set provider in order to initialize OpenAIEmbeddingProvider."
            )

        if config.provider != "openai":
            raise ValueError(
                "OpenAIEmbeddingProvider must be initialized with provider `openai`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
            )
        self.client = OpenAI()
        self.async_client = AsyncOpenAI()

        if config.rerank_model:
            raise ValueError(
                "OpenAIEmbeddingProvider does not support separate reranking."
            )

        if config.base_model and "openai/" in config.base_model:
            self.base_model = config.base_model.split("/")[-1]
        else:
            self.base_model = config.base_model
        self.base_dimension = config.base_dimension

        if not self.base_model:
            raise ValueError(
                "Must set base_model in order to initialize OpenAIEmbeddingProvider."
            )

        if self.base_model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(
                f"OpenAI embedding model {self.base_model} not supported."
            )

        if self.base_dimension:
            if (
                self.base_dimension
                not in OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[
                    self.base_model
                ]
            ):
                raise ValueError(
                    f"Dimensions {self.base_dimension} for {self.base_model} are not supported"
                )
        else:
            # If base_dimension is not set, use the largest available dimension for the model
            self.base_dimension = max(
                OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[self.base_model]
            )

    def _get_dimensions(self):
        return (
            NOT_GIVEN
            if self.base_model == "text-embedding-ada-002"
            else self.base_dimension
            or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[self.base_model][-1]
        )

    def _get_embedding_kwargs(self, **kwargs):
        return {
            "model": self.base_model,
            "dimensions": self._get_dimensions(),
        } | kwargs

    async def _execute_task(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))

        try:
            response = await self.async_client.embeddings.create(
                input=texts,
                **kwargs,
            )
            return [data.embedding for data in response.data]
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _execute_task_sync(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        kwargs = self._get_embedding_kwargs(**task.get("kwargs", {}))
        try:
            response = self.client.embeddings.create(
                input=texts,
                **kwargs,
            )
            return [data.embedding for data in response.data]
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
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
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
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
        texts: list[str],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
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
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
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
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
    ):
        return results[:limit]

    async def arerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
    ):
        return results[:limit]

    def tokenize_string(self, text: str, model: str) -> list[int]:
        if model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(f"OpenAI embedding model {model} not supported.")
        encoding = tiktoken.get_encoding(
            OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER[model]
        )
        return encoding.encode(text)
