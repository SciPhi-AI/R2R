import asyncio
import logging
import os
from typing import Any, List

from ollama import AsyncClient, Client

from r2r.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
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

    async def _execute_task(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        purpose = task.get("purpose", EmbeddingPurpose.INDEX)
        text = self.prefixes.get(purpose, "") + text

        try:
            response = await self.aclient.embeddings(
                prompt=text, model=self.base_model
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

    def _execute_task_sync(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        purpose = task.get("purpose", EmbeddingPurpose.INDEX)
        text = self.prefixes.get(purpose, "") + text

        try:
            response = self.client.embeddings(
                prompt=text, model=self.base_model
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
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
                "OllamaEmbeddingProvider only supports search stage."
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
                "OllamaEmbeddingProvider only supports search stage."
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
                "OllamaEmbeddingProvider only supports search stage."
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
    ) -> list[VectorSearchResult]:
        return results[:limit]

    def tokenize_string(
        self, text: str, model: str, stage: EmbeddingProvider.PipeStage
    ) -> list[int]:
        raise NotImplementedError(
            "Tokenization is not supported by OllamaEmbeddingProvider."
        )
