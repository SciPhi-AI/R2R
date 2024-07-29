import logging
import os
from typing import Any

from openai import AsyncOpenAI, OpenAI

from r2r.base.abstractions.llm import GenerationConfig
from r2r.base.providers.llm import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    def __init__(self, config: LLMConfig, *args, **kwargs) -> None:
        super().__init__(config)
        if config.provider != "openai":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "OpenAILLMProvider must be initialized with config with `openai` provider."
            )
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OpenAI API key not found")
            raise ValueError(
                "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."
            )
        self.async_client = AsyncOpenAI()
        self.client = OpenAI()
        logger.debug("OpenAILLMProvider initialized successfully")

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            "max_tokens": generation_config.max_tokens_to_sample,
        }
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions
        if generation_config.tools is not None:
            args["tools"] = generation_config.tools
        return args

    async def _execute_task(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        logger.debug(f"Executing async OpenAI task with args: {args}")
        try:
            response = await self.async_client.chat.completions.create(**args)
            logger.debug("Async OpenAI task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Async OpenAI task execution failed: {str(e)}")
            raise

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        logger.debug(f"Executing sync OpenAI task with args: {args}")
        try:
            response = self.client.chat.completions.create(**args)
            logger.debug("Sync OpenAI task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Sync OpenAI task execution failed: {str(e)}")
            raise
