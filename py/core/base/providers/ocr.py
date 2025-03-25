import asyncio
import logging
import random
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from litellm import AuthenticationError

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class OCRConfig(ProviderConfig):
    provider: Optional[str] = None
    model: Optional[str] = None
    concurrent_request_limit: int = 256
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 64.0

    def validate_config(self) -> None:
        if not self.provider:
            raise ValueError("Provider must be set.")
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["mistral"]


class OCRProvider(Provider):
    def __init__(self, config: OCRConfig) -> None:
        if not isinstance(config, OCRConfig):
            raise ValueError(
                "OCRProvider must be initialized with a `OCRConfig`."
            )
        logger.info(f"Initializing OCRProvider with config: {config}")
        super().__init__(config)
        self.config: OCRConfig = config
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

    @abstractmethod
    async def process_pdf(self, file_path: str | None = None, file_content: bytes | None = None) -> Any:
        pass
