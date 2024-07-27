import asyncio
import logging
import random
from typing import Any, Generator, Union

from r2r.base import (
    LLMChatCompletion,
    LLMChatCompletionChunk,
    LLMConfig,
    LLMProvider,
)
from r2r.base.abstractions.llm import GenerationConfig

logger = logging.getLogger(__name__)


class LiteLLMProvider(LLMProvider):
    """A concrete class for creating LiteLLMProvider models with request throttling."""

    def __init__(
        self,
        config: LLMConfig,
        *args,
        **kwargs,
    ) -> None:
        try:
            from litellm import acompletion, completion

            self.litellm_completion = completion
            self.litellm_acompletion = acompletion
        except ImportError as e:
            raise ImportError(
                "Error, `litellm` is required to run ThrottledLiteLLM. Please install it using `pip install litellm`."
            ) from e
        super().__init__(config)

        # Initialize semaphore and request queue
        self.semaphore = asyncio.Semaphore(config.concurrency_limit)
        self.request_queue = asyncio.Queue()

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

    async def execute_task_with_backoff(self, task: dict[str, Any]):
        retries = 0
        backoff = self.config.initial_backoff
        while retries < self.config.max_retries:
            try:
                async with self.semaphore:
                    response = await asyncio.wait_for(
                        self.litellm_acompletion(**task["args"]),
                        timeout=30,
                    )
                return response
            except Exception as e:
                logger.warning(
                    f"Request failed (attempt {retries + 1}): {str(e)}"
                )
                retries += 1
                if retries == self.config.max_retries:
                    raise Exception(
                        f"Max retries reached. Last error: {str(e)}"
                    )
                await asyncio.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, self.config.max_backoff)

    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        if generation_config.stream:
            raise ValueError(
                "Stream must be set to False to use the `get_completion` method."
            )
        return self._get_completion(messages, generation_config, **kwargs)

    def get_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Generator[LLMChatCompletionChunk, None, None]:
        if not generation_config.stream:
            raise ValueError(
                "Stream must be set to True to use the `get_completion_stream` method."
            )
        return self._get_completion(messages, generation_config, **kwargs)

    def extract_content(self, response: LLMChatCompletion) -> str:
        return response.choices[0].message.content

    def _get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[
        LLMChatCompletion, Generator[LLMChatCompletionChunk, None, None]
    ]:
        args = self._get_base_args(generation_config)
        args["messages"] = messages

        args = {**args, **kwargs}
        response = self.litellm_completion(**args)

        if not generation_config.stream:
            return LLMChatCompletion(**response.dict())
        else:
            return self._get_chat_completion(response)

    def _get_chat_completion(
        self,
        response: Any,
    ) -> Generator[LLMChatCompletionChunk, None, None]:
        for part in response:
            yield LLMChatCompletionChunk(**part.dict())

    def _get_base_args(
        self,
        generation_config: GenerationConfig,
        prompt=None,
    ) -> dict:
        """Get the base arguments for the LiteLLMProvider API."""
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            "max_tokens": generation_config.max_tokens_to_sample,
            "api_base": generation_config.api_base,
        }

        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        if generation_config.tools is not None:
            args["tools"] = generation_config.tools

        return args

    async def aget_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        if generation_config.stream:
            raise ValueError(
                "Stream must be set to False to use the `aget_completion` method."
            )
        return await self._aget_completion(
            messages, generation_config, **kwargs
        )

    async def _aget_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[LLMChatCompletion, LLMChatCompletionChunk]:
        args = self._get_base_args(generation_config)
        args["messages"] = messages

        if generation_config.tools is not None:
            args["tools"] = generation_config.tools

        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        args = {**args, **kwargs}

        queue_processor = asyncio.create_task(self.process_queue())
        future = asyncio.Future()
        await self.request_queue.put({"args": args, "future": future})

        try:
            response = await future
            return LLMChatCompletion(**response.dict())
        except Exception as e:
            logger.error(f"Completion generation failed: {str(e)}")
            raise
        finally:
            await self.request_queue.join()
            queue_processor.cancel()
