import asyncio
import logging
import random
import time
from abc import abstractmethod
from enum import Enum
from typing import Any, Optional

from litellm import AuthenticationError

from core.base.abstractions import VectorQuantizationSettings

from ..abstractions import (
    ChunkSearchResult,
    EmbeddingPurpose,
    default_embedding_prefixes,
)
from .base import Provider, ProviderConfig

logger = logging.getLogger()


class EmbeddingConfig(ProviderConfig):
    provider: str
    base_model: str
    base_dimension: int | float
    rerank_model: Optional[str] = None
    rerank_url: Optional[str] = None
    batch_size: int = 1
    prefixes: Optional[dict[str, str]] = None
    add_title_as_prefix: bool = True
    concurrent_request_limit: int = 256
    max_retries: int = 3
    initial_backoff: float = 1
    max_backoff: float = 64.0
    quantization_settings: VectorQuantizationSettings = (
        VectorQuantizationSettings()
    )

    ## deprecated
    rerank_dimension: Optional[int] = None
    rerank_transformer_type: Optional[str] = None

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["litellm", "openai", "ollama"]


class EmbeddingProvider(Provider):
    class Step(Enum):
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
        self.current_requests = 0

    async def _execute_with_backoff_async(self, task: dict[str, Any]):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                async with self.semaphore:
                    return await self._execute_task(task)
            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.config.max_retries:
                    raise
                await asyncio.sleep(random.uniform(0, backoff))
                backoff = min(backoff * 2, self.config.max_backoff)

    def _execute_with_backoff_sync(self, task: dict[str, Any]):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                return self._execute_task_sync(task)
            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.config.max_retries:
                    raise
                time.sleep(random.uniform(0, backoff))
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
        stage: Step = Step.BASE,
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
        stage: Step = Step.BASE,
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
        stage: Step = Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ):
        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
        }
        return await self._execute_with_backoff_async(task)

    def get_embeddings(
        self,
        texts: list[str],
        stage: Step = Step.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> list[list[float]]:
        task = {
            "texts": texts,
            "stage": stage,
            "purpose": purpose,
        }
        return self._execute_with_backoff_sync(task)

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: Step = Step.RERANK,
        limit: int = 10,
    ):
        pass

    @abstractmethod
    async def arerank(
        self,
        query: str,
        results: list[ChunkSearchResult],
        stage: Step = Step.RERANK,
        limit: int = 10,
    ):
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
