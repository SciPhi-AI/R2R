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
    # Per-model concurrency limits for different LLM types
    fast_llm_concurrent_request_limit: Optional[int] = None
    quality_llm_concurrent_request_limit: Optional[int] = None
    vlm_concurrent_request_limit: Optional[int] = None
    audio_lm_concurrent_request_limit: Optional[int] = None
    reasoning_llm_concurrent_request_limit: Optional[int] = None
    planning_llm_concurrent_request_limit: Optional[int] = None
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 64.0
    request_timeout: float = 15.0

    def validate_config(self) -> None:
        if not self.provider:
            raise ValueError("Provider must be set.")
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["anthropic", "litellm", "openai", "r2r"]
    
    def get_concurrent_request_limit(self, model: Optional[str] = None) -> int:
        """Get the appropriate concurrency limit based on the model being used.
        
        Args:
            model: The model identifier (e.g., from app.fast_llm, app.quality_llm)
            
        Returns:
            The concurrency limit to use for the given model
        """
        if not model or not self.app:
            return self.concurrent_request_limit
            
        # Check if the model matches any of the configured LLM types
        if self.app.fast_llm and model == self.app.fast_llm:
            return self.fast_llm_concurrent_request_limit or self.concurrent_request_limit
        elif self.app.quality_llm and model == self.app.quality_llm:
            return self.quality_llm_concurrent_request_limit or self.concurrent_request_limit
        elif self.app.vlm and model == self.app.vlm:
            return self.vlm_concurrent_request_limit or self.concurrent_request_limit
        elif self.app.audio_lm and model == self.app.audio_lm:
            return self.audio_lm_concurrent_request_limit or self.concurrent_request_limit
        elif self.app.reasoning_llm and model == self.app.reasoning_llm:
            return self.reasoning_llm_concurrent_request_limit or self.concurrent_request_limit
        elif self.app.planning_llm and model == self.app.planning_llm:
            return self.planning_llm_concurrent_request_limit or self.concurrent_request_limit
        
        # Default to the global limit if no specific match
        return self.concurrent_request_limit


class CompletionProvider(Provider):
    def __init__(self, config: CompletionConfig) -> None:
        if not isinstance(config, CompletionConfig):
            raise ValueError(
                "CompletionProvider must be initialized with a `CompletionConfig`."
            )
        logger.info(f"Initializing CompletionProvider with config: {config}")
        super().__init__(config)
        self.config: CompletionConfig = config
        # Use a single semaphore for backward compatibility, but track per-model limits
        self.semaphore = asyncio.Semaphore(config.concurrent_request_limit)
        self.thread_pool = ThreadPoolExecutor(
            max_workers=config.concurrent_request_limit
        )
        # Store per-model semaphores for different concurrency limits
        self._model_semaphores: dict[str, asyncio.Semaphore] = {}
    
    def _get_semaphore_for_model(self, model: Optional[str] = None) -> asyncio.Semaphore:
        """Get the appropriate semaphore for the given model.
        
        Args:
            model: The model identifier
            
        Returns:
            The semaphore to use for concurrency control
        """
        if not model:
            return self.semaphore
            
        # Check if we have a specific limit for this model
        limit = self.config.get_concurrent_request_limit(model)
        if limit == self.config.concurrent_request_limit:
            # Use the default semaphore if the limit is the same
            return self.semaphore
            
        # Create or get a model-specific semaphore
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(limit)
        return self._model_semaphores[model]

    async def _execute_with_backoff_async(
        self,
        task: dict[str, Any],
        apply_timeout: bool = False,
        model: Optional[str] = None,
    ):
        retries = 0
        backoff = self.config.initial_backoff
        semaphore = self._get_semaphore_for_model(model)
        while retries < self.config.max_retries:
            try:
                # A semaphore allows us to limit concurrent requests
                async with semaphore:
                    if not apply_timeout:
                        return await self._execute_task(task)

                    try:  # Use asyncio.wait_for to set a timeout for the request
                        return await asyncio.wait_for(
                            self._execute_task(task),
                            timeout=self.config.request_timeout,
                        )
                    except asyncio.TimeoutError as e:
                        raise TimeoutError(
                            f"Request timed out after {self.config.request_timeout} seconds"
                        ) from e
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
        self, task: dict[str, Any], model: Optional[str] = None
    ) -> AsyncGenerator[Any, None]:
        retries = 0
        backoff = self.config.initial_backoff
        semaphore = self._get_semaphore_for_model(model)
        while retries < self.config.max_retries:
            try:
                async with semaphore:
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

    def _execute_with_backoff_sync(
        self,
        task: dict[str, Any],
        apply_timeout: bool = False,
    ):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            if not apply_timeout:
                return self._execute_task_sync(task)

            try:
                future = self.thread_pool.submit(self._execute_task_sync, task)
                return future.result(timeout=self.config.request_timeout)
            except TimeoutError as e:
                raise TimeoutError(
                    f"Request timed out after {self.config.request_timeout} seconds"
                ) from e
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
        apply_timeout: bool = False,
        **kwargs,
    ) -> LLMChatCompletion:
        task = {
            "messages": messages,
            "generation_config": generation_config,
            "kwargs": kwargs,
        }
        # Extract model from generation_config for concurrency control
        model = getattr(generation_config, 'model', None)
        response = await self._execute_with_backoff_async(
            task=task, apply_timeout=apply_timeout, model=model
        )
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
        # Extract model from generation_config for concurrency control
        model = getattr(generation_config, 'model', None)
        async for chunk in self._execute_with_backoff_async_stream(task, model=model):
            if isinstance(chunk, dict):
                yield LLMChatCompletionChunk(**chunk)
                continue

            if chunk.choices and len(chunk.choices) > 0:
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
