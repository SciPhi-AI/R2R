import logging
import os
from typing import Any

import litellm
from litellm import acompletion, completion

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger()


class LiteLLMCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)

        # Allow LiteLLM to automatically drop parameters that are not supported by the model
        litellm.drop_params = True

        self.acompletion = acompletion
        self.completion = completion
        self.api_base = os.getenv("API_BASE")

        if not config.provider:
            raise ValueError(
                "Must set provider in order to initialize `LiteLLMEmbeddingProvider`."
            )
        if config.provider != "litellm":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "LiteLLMCompletionProvider must be initialized with config with `litellm` provider."
            )

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            "max_tokens": generation_config.max_tokens_to_sample,
        }
        if generation_config.api_base is not None:
            args["api_base"] = generation_config.api_base
        else:
            logger.info(f"Using API base: {self.api_base}")
            args["api_base"] = self.api_base
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions
        if generation_config.tools is not None:
            args["tools"] = generation_config.tools
        if generation_config.response_format is not None:
            args["response_format"] = generation_config.response_format
        return args

    async def _execute_task(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        return await self.acompletion(**args)

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        try:
            return self.completion(**args)
        except Exception as e:
            logger.error(f"Sync LiteLLM task execution failed: {str(e)}")
            raise
