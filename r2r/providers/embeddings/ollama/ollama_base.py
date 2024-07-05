import asyncio
import logging
import os
from typing import Any, List

from ollama import AsyncClient, Client

from r2r.base import EmbeddingConfig, EmbeddingProvider, VectorSearchResult

logger = logging.getLogger(__name__)


class EmbeddingFailedException(Exception):
    """Exception raised when embedding generation fails."""

    pass


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

        self.request_queue = asyncio.Queue()
        self.concurrency_limit = 10
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)

    async def process_queue(self):
        while True:
            task = await self.request_queue.get()
            try:
                result = await self.execute_task_with_backoff(task)
                task["future"].set_result(result)
            except Exception as e:
                task["future"].set_exception(e)
            finally:
                self.request_queue.task_done()

    async def execute_task_with_backoff(
        self, task: dict[str, Any]
    ) -> List[float]:
        async with self.semaphore:
            try:
                response = await asyncio.wait_for(
                    self.aclient.embeddings(
                        prompt=task["text"], model=self.base_model
                    ),
                    timeout=30,
                )
                return response["embedding"]
            except Exception as e:
                logger.error(
                    f"Embedding generation failed for text: {task['text'][:50]}... Error: {str(e)}"
                )
                raise EmbeddingFailedException(
                    f"Failed to generate atleast one embedding. Error: {str(e)}"
                ) from e

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> List[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OllamaEmbeddingProvider only supports search stage."
            )

        response = self.client.embeddings(prompt=text, model=self.base_model)
        return response["embedding"]

    def get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> List[List[float]]:
        return [self.get_embedding(text, stage) for text in texts]

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> List[List[float]]:
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

        try:
            results = await asyncio.gather(*futures, return_exceptions=True)
            # Check if any result is an exception and raise it
            for result in results:
                if isinstance(result, Exception):
                    raise result
            return results
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            raise
        finally:
            await self.request_queue.join()
            # Check if any result is an exception and raise it
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Embedding generation failed: {str(result)}")
                    raise result

            queue_processor.cancel()

    def rerank(
        self,
        query: str,
        results: List[VectorSearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ) -> List[VectorSearchResult]:
        return results[:limit]

    def tokenize_string(
        self, text: str, model: str, stage: EmbeddingProvider.PipeStage
    ) -> List[int]:
        raise NotImplementedError(
            "Tokenization is not supported by OllamaEmbeddingProvider."
        )
