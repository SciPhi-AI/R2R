import logging
import os
from typing import Any

from core.base import (
    ChunkSearchResult,
    EmbeddingConfig,
    EmbeddingProvider,
    R2RException,
)

logger = logging.getLogger()


class TwelveLabsEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by TwelveLabs Marengo.

    Marengo produces 512-dimensional embeddings in a shared multimodal space,
    which lets text queries retrieve over video/image/audio content embedded
    with the same model. This provider implements the text path used by R2R's
    search and ingestion pipelines.
    """

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize "
                "`TwelveLabsEmbeddingProvider`."
            )
        if provider != "twelvelabs":
            raise ValueError(
                "TwelveLabsEmbeddingProvider must be initialized with "
                "provider `twelvelabs`."
            )
        if config.rerank_model:
            raise ValueError(
                "TwelveLabsEmbeddingProvider does not support separate "
                "reranking."
            )

        try:
            from twelvelabs import AsyncTwelveLabs, TwelveLabs
        except ImportError as e:
            raise ImportError(
                "Error: Could not import the `twelvelabs` package. "
                "Please install it with `pip install twelvelabs`."
            ) from e

        api_key = config.api_key or os.getenv("TWELVELABS_API_KEY")
        if not api_key:
            raise ValueError(
                "Must set TWELVELABS_API_KEY in order to initialize "
                "TwelveLabsEmbeddingProvider."
            )

        # Marengo embeddings are fixed at 512 dimensions.
        self.base_model = config.base_model or "marengo3.0"
        self.base_dimension = config.base_dimension
        self.batch_size = config.batch_size or 32

        self.client = TwelveLabs(api_key=api_key)
        self.aclient = AsyncTwelveLabs(api_key=api_key)

    def _embedding_from_response(self, response: Any) -> list[float]:
        segments = response.text_embedding.segments
        if not segments:
            raise R2RException(
                "TwelveLabs returned no embedding segments.", 400
            )
        return segments[0].float_

    async def _execute_task(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        try:
            embeddings: list[list[float]] = []
            for text in texts:
                response = await self.aclient.embed.create(
                    model_name=self.base_model, text=text
                )
                embeddings.append(self._embedding_from_response(response))
            return embeddings
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise R2RException(error_msg, 400) from e

    def _execute_task_sync(self, task: dict[str, Any]) -> list[list[float]]:
        texts = task["texts"]
        try:
            embeddings: list[list[float]] = []
            for text in texts:
                response = self.client.embed.create(
                    model_name=self.base_model, text=text
                )
                embeddings.append(self._embedding_from_response(response))
            return embeddings
        except Exception as e:
            error_msg = f"Error getting embeddings: {str(e)}"
            logger.error(error_msg)
            raise R2RException(error_msg, 400) from e

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "TwelveLabsEmbeddingProvider only supports search stage."
            )

        task = {"texts": [text], "stage": stage}
        result = await self._execute_with_backoff_async(task)
        return result[0]

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        **kwargs,
    ) -> list[float]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "TwelveLabsEmbeddingProvider only supports search stage."
            )

        task = {"texts": [text], "stage": stage}
        result = self._execute_with_backoff_sync(task)
        return result[0]

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "TwelveLabsEmbeddingProvider only supports search stage."
            )

        task = {"texts": texts, "stage": stage}
        return await self._execute_with_backoff_async(task)

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.BASE,
        **kwargs,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.Step.BASE:
            raise ValueError(
                "TwelveLabsEmbeddingProvider only supports search stage."
            )

        task = {"texts": texts, "stage": stage}
        return self._execute_with_backoff_sync(task)

    def rerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
    ) -> list[ChunkSearchResult]:
        return results[:limit]

    async def arerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: EmbeddingProvider.Step = EmbeddingProvider.Step.RERANK,
        limit: int = 10,
    ):
        return results[:limit]
