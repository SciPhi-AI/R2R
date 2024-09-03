import logging
from typing import Any

from core.base.abstractions.llm import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger(__name__)


class LiteCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        try:
            from litellm import acompletion, completion, OllamaConfig

            if config.generation_config.add_generation_kwargs:
                # We have provider-specific generation arguments, let's set them
                # 1. Get the possible arguments for the OllamaConfig class
                import inspect

                ollama_config_options = inspect.signature(
                    OllamaConfig
                ).parameters
                # 2. Collect the valid provider-specific arguments or complain
                arguments_to_set = {}
                given_custom_params = (
                    config.generation_config.add_generation_kwargs
                )
                for key, value in given_custom_params.items():
                    if key in ollama_config_options:
                        arguments_to_set[key] = value
                    else:
                        logger.error(
                            "Invalid provider-specific argument: %s (with value %s)",
                            key,
                            value,
                        )
                # 3. Set the valid provider-specific arguments
                OllamaConfig(**arguments_to_set)
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

        try:
            response = await self.acompletion(**args)
            return response
        except Exception as e:
            raise

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
