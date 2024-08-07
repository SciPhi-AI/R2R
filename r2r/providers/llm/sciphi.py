import os
import logging
from typing import Any

from r2r.base.abstractions.llm import GenerationConfig
from r2r.base.providers.llm import CompletionConfig
from .litellm import LiteCompletionProvider

logger = logging.getLogger(__name__)


class SciPhiCompletionProvider(LiteCompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        if config.provider != "sciphi":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "SciPhiCompletionProvider must be initialized with config with `sciphi` provider."
            )
        config_copy = config.copy()
        config_copy.provider = "litellm"
        super().__init__(config_copy)

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

    def _validate_model(self, generation_config: GenerationConfig) -> None:
        # if generation_config.model != "sciphi/gpt-4o-mini":
        #     raise ValueError(
        #         "SciPhiCompletionProvider must be initialized with `sciphi/gpt-4o-mini` model."
        #     )
        generation_config.model = "openai/gpt-4o-mini"

    def _set_api_key(self, key: str) -> str:
        original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = key
        return original_key

    async def _execute_task(self, task: dict[str, Any]):
        generation_config = task["generation_config"]
        self._validate_model(generation_config)
        original_key = self._set_api_key(os.getenv("SCIPHI_PRIVATE_API_KEY"))
        try:
            return await super()._execute_task(task)
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            raise
        finally:
            os.environ["OPENAI_API_KEY"] = original_key

    def _execute_task_sync(self, task: dict[str, Any]):
        print('task = ', task)
        generation_config = task["generation_config"]
        self._validate_model(generation_config)
        original_key = self._set_api_key(os.getenv("SCIPHI_PRIVATE_API_KEY"))
        try:
            return super()._execute_task_sync(task)
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            raise
        finally:
            os.environ["OPENAI_API_KEY"] = original_key