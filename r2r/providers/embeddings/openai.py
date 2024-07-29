import asyncio
import logging
import os
from typing import Any, List

from openai import AsyncOpenAI, AuthenticationError, OpenAI
from openai._types import NOT_GIVEN

from r2r.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


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

    async def _execute_task(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        try:
            response = await self.async_client.embeddings.create(
                input=[text],
                model=self.base_model,
                dimensions=self._get_dimensions(),
            )
            return response.data[0].embedding
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e
        except Exception as e:
            raise ValueError(f"Error getting embedding: {str(e)}")

    def _execute_task_sync(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        try:
            return (
                self.client.embeddings.create(
                    input=[text],
                    model=self.base_model,
                    dimensions=self._get_dimensions(),
                )
                .data[0]
                .embedding
            )
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e
        except Exception as e:
            raise ValueError(f"Error getting embedding: {str(e)}")

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return await self._execute_with_backoff_async(task)

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return self._execute_with_backoff_sync(task)

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[List[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
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
    ) -> List[List[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
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

    def tokenize_string(self, text: str, model: str) -> list[int]:
        try:
            import tiktoken
        except ImportError:
            raise ValueError(
                "Must download tiktoken library to run `tokenize_string`."
            )
        if model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(f"OpenAI embedding model {model} not supported.")
        encoding = tiktoken.get_encoding(
            OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER[model]
        )
        return encoding.encode(text)
