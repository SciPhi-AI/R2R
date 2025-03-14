import asyncio
import logging
import random
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Generator, Optional

from litellm import AuthenticationError

from core.base.abstractions import (
    GenerationConfig,
    LLMChatCompletion,
    LLMChatCompletionChunk,
)

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class CompletionConfig(ProviderConfig):
    provider: Optional[str] = None
    generation_config: Optional[GenerationConfig] = None
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
        return ["anthropic", "litellm", "openai", "r2r"]


class CompletionProvider(Provider):
    def __init__(self, config: CompletionConfig) -> None:
        if not isinstance(config, CompletionConfig):
            raise ValueError(
                "CompletionProvider must be initialized with a `CompletionConfig`."
            )
        logger.info(f"Initializing CompletionProvider with config: {config}")
        super().__init__(config)
        self.config: CompletionConfig = config
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
            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning(
                    f"Streaming request failed (attempt {retries + 1}): {str(e)}"
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
                time.sleep(random.uniform(0, backoff))
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
            if isinstance(chunk, dict):
                yield LLMChatCompletionChunk(**chunk)
                continue

            chunk.choices[0].finish_reason = (
                chunk.choices[0].finish_reason
                if chunk.choices[0].finish_reason != ""
                else None
            )  # handle error output conventions
            chunk.choices[0].finish_reason = (
                chunk.choices[0].finish_reason
                if chunk.choices[0].finish_reason != "eos"
                else "stop"
            )  # hardcode `eos` to `stop` for consistency
            try:
                yield LLMChatCompletionChunk(**(chunk.dict()))
            except Exception as e:
                logger.error(f"Error parsing chunk: {e}")
                yield LLMChatCompletionChunk(**(chunk.as_dict()))

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
