import asyncio
import logging
import random

import ollama
from ollama import AsyncClient

from r2r.base import EmbeddingConfig, EmbeddingProvider, VectorSearchResult

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
        self.client = AsyncClient()
        self.request_queue = asyncio.Queue()
        self.max_retries = 5
        self.initial_backoff = 1
        self.max_backoff = 60
        self.concurrency_limit = 10
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)

    async def process_queue(self):
        while True:
            task = await self.request_queue.get()
            await self.execute_task_with_backoff(task)
            self.request_queue.task_done()

    async def execute_task_with_backoff(self, task: dict[str, Any]):
        retries = 0
        backoff = self.initial_backoff
        while retries < self.max_retries:
            try:
                async with self.semaphore:
                    response = await asyncio.wait_for(
                        self.client.embeddings(
                            prompt=task["text"], model=self.base_model
                        ),
                        timeout=30,
                    )
                task["future"].set_result(response["embedding"])
                return
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.max_retries:
                    task["future"].set_exception(e)
                    return
                await asyncio.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, self.max_backoff)

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
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )

        future = asyncio.Future()
        await self.request_queue.put({"text": text, "future": future})
        return await future

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        return [self.get_embedding(text, stage) for text in texts]

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )

        queue_processor = asyncio.create_task(self.process_queue())
        futures = []
        for text in texts:
            future = asyncio.Future()
            await self.request_queue.put({"text": text, "future": future})
            futures.append(future)

        results = await asyncio.gather(*futures, return_exceptions=True)
        await self.request_queue.join()
        queue_processor.cancel()

        return [
            result for result in results if not isinstance(result, Exception)
        ]

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
        """Tokenizes the input string."""
        raise NotImplementedError(
            "Tokenization is not supported by OllamaEmbeddingProvider."
        )
