import asyncio
import logging
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Generator, Optional

from r2r.base.abstractions.llm import (
    GenerationConfig,
    LLMChatCompletion,
    LLMChatCompletionChunk,
)

from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class LLMConfig(ProviderConfig):
    provider: Optional[str] = None
    generation_config: Optional[GenerationConfig] = None
    concurrency_limit: int = 16
    max_retries: int = 2
    initial_backoff: float = 1.0
    max_backoff: float = 60.0

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("Provider must be set.")
        if self.provider and self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["litellm", "openai"]


class LLMProvider(Provider):
    def __init__(self, config: LLMConfig) -> None:
        if not isinstance(config, LLMConfig):
            raise ValueError(
                "LLMProvider must be initialized with a `LLMConfig`."
            )
        logger.info(f"Initializing LLMProvider with config: {config}")
        super().__init__(config)
        self.config: LLMConfig = config
        self.semaphore = asyncio.Semaphore(config.concurrency_limit)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=config.concurrency_limit
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

    async def _execute_with_backoff_async_stream(
        self, task: dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                async with self.semaphore:
                    async for chunk in await self._execute_task(task):
                        yield chunk
                return  # Successful completion of the stream
            except Exception as e:
                logger.warning(
                    f"Streaming request failed (attempt {retries + 1}): {str(e)}"
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

    def _execute_with_backoff_sync_stream(
        self, task: dict[str, Any]
    ) -> Generator[Any, None, None]:
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                yield from self._execute_task_sync(task)
                return  # Successful completion of the stream
            except Exception as e:
                logger.warning(
                    f"Streaming request failed (attempt {retries + 1}): {str(e)}"
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

    async def aget_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        task = {
            "messages": messages,
            "generation_config": generation_config,
            "kwargs": kwargs,
        }
        response = await self._execute_with_backoff_async(task)
        return LLMChatCompletion(**response.dict())

    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        task = {
            "messages": messages,
            "generation_config": generation_config,
            "kwargs": kwargs,
        }
        response = self._execute_with_backoff_sync(task)
        return LLMChatCompletion(**response.dict())

    async def aget_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> AsyncGenerator[LLMChatCompletionChunk, None]:
        generation_config.stream = True
        task = {
            "messages": messages,
            "generation_config": generation_config,
            "kwargs": kwargs,
        }
        async for chunk in self._execute_with_backoff_async_stream(task):
            yield LLMChatCompletionChunk(**chunk.dict())

    def get_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Generator[LLMChatCompletionChunk, None, None]:
        generation_config.stream = True
        task = {
            "messages": messages,
            "generation_config": generation_config,
            "kwargs": kwargs,
        }
        for chunk in self._execute_with_backoff_sync_stream(task):
            yield LLMChatCompletionChunk(**chunk.dict())
