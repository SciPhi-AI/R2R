import logging
from typing import Any

from core.base.abstractions.llm import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger(__name__)


class LiteCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        try:
            from litellm import acompletion, completion

            self.acompletion = acompletion
            self.completion = completion
            logger.debug("LiteLLM imported successfully")
        except ImportError:
            logger.error("Failed to import LiteLLM")
            raise ImportError(
                "Please install the `litellm` package to use the LiteCompletionProvider."
            )

        if config.provider != "litellm":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "LiteCompletionProvider must be initialized with config with `litellm` provider."
            )

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
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

    async def _execute_task(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        response = await self.acompletion(**args)
        return response

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}

        try:
            response = self.completion(**args)
            logger.debug("Sync LiteLLM task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Sync LiteLLM task execution failed: {str(e)}")
            raise
