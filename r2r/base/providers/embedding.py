import asyncio
import logging
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Optional

from ..abstractions.embedding import (
    EmbeddingPurpose,
    default_embedding_prefixes,
)
from ..abstractions.search import VectorSearchResult
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class EmbeddingConfig(ProviderConfig):
    provider: Optional[str] = None
    base_model: Optional[str] = None
    base_dimension: Optional[int] = None
    rerank_model: Optional[str] = None
    rerank_dimension: Optional[int] = None
    rerank_transformer_type: Optional[str] = None
    batch_size: int = 1
    prefixes: Optional[dict[str, str]] = None
    add_title_as_prefix: bool = True
    concurrent_request_limit: int = 16
    max_retries: int = 2
    initial_backoff: float = 1.0
    max_backoff: float = 60.0

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return [None, "litellm", "openai", "ollama", "sentence-transformers"]


class EmbeddingProvider(Provider):
    class PipeStage(Enum):
        BASE = 1
        RERANK = 2

    def __init__(self, config: EmbeddingConfig):
        if not isinstance(config, EmbeddingConfig):
            raise ValueError(
                "EmbeddingProvider must be initialized with a `EmbeddingConfig`."
            )
        logger.info(f"Initializing EmbeddingProvider with config {config}.")

        super().__init__(config)
        self.config: EmbeddingConfig = config
        self.semaphore = asyncio.Semaphore(config.concurrent_request_limit)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=config.concurrent_request_limit
        )

    async def _execute_with_backoff_async(self, task: dict[str, Any]):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                async with self.semaphore:
                    return await self._execute_task(task)
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.config.max_retries:
                    raise
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.config.max_backoff)

    def _execute_with_backoff_sync(self, task: dict[str, Any]):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                return self._execute_task_sync(task)
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.config.max_retries:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 2, self.config.max_backoff)

    @abstractmethod
    async def _execute_task(self, task: dict[str, Any]):
        pass

    @abstractmethod
    def _execute_task_sync(self, task: dict[str, Any]):
        pass

    async def async_get_embedding(
        self,
        text: str,
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return await self._execute_with_backoff_async(task)

    def get_embedding(
        self,
        text: str,
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return self._execute_with_backoff_sync(task)

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
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
        texts: list[str],
        stage: PipeStage = PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
            }
            for text in texts
        ]
        return [self._execute_with_backoff_sync(task) for task in tasks]

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: PipeStage = PipeStage.RERANK,
        limit: int = 10,
    ):
        pass

    @abstractmethod
    def tokenize_string(
        self, text: str, model: str, stage: PipeStage
    ) -> list[int]:
        pass

    def set_prefixes(self, config_prefixes: dict[str, str], base_model: str):
        self.prefixes = {}

        for t, p in config_prefixes.items():
            purpose = EmbeddingPurpose(t.lower())
            self.prefixes[purpose] = p

        if base_model in default_embedding_prefixes:
            for t, p in default_embedding_prefixes[base_model].items():
                if t not in self.prefixes:
                    self.prefixes[t] = p
