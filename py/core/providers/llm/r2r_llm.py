import logging
from typing import Any

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

from .anthropic import AnthropicCompletionProvider
from .litellm import LiteLLMCompletionProvider
from .openai import OpenAICompletionProvider

logger = logging.getLogger(__name__)


class R2RCompletionProvider(CompletionProvider):
    """
    A provider that Routes to the Right LLM provider (R2R):
      - If `generation_config.model` starts with "anthropic/", call AnthropicCompletionProvider.
      - If it starts with one of OpenAI-like prefixes ("openai/", "azure/", "deepseek/", "ollama/", "lmstudio/")
        or has no prefix (e.g. "gpt-4", "gpt-3.5"), call OpenAICompletionProvider.
      - Otherwise, fallback to LiteLLMCompletionProvider.
    """

    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        """
        Initialize sub-providers for OpenAI, Anthropic, and LiteLLM.
        """
        super().__init__(config)
        self.config = config

        # Create sub-providers with the same config.
        logger.info("Initializing R2RCompletionProvider...")
        self._openai_provider = OpenAICompletionProvider(
            self.config, *args, **kwargs
        )
        self._anthropic_provider = AnthropicCompletionProvider(
            self.config, *args, **kwargs
        )
        self._litellm_provider = LiteLLMCompletionProvider(
            self.config, *args, **kwargs
        )
        logger.debug(
            "R2RCompletionProvider initialized with OpenAI, Anthropic, and LiteLLM sub-providers."
        )

    def _choose_subprovider_by_model(
        self, model_name: str
    ) -> CompletionProvider:
        """
        Decide which underlying sub-provider to call based on the model name (prefix).
        """
        # Anthropic route
        if model_name.startswith("anthropic/"):
            return self._anthropic_provider

        # OpenAI route
        openai_like_prefixes = (
            "openai/",
            "azure/",
            "deepseek/",
            "ollama/",
            "lmstudio/",
        )
        if (
            model_name.startswith(openai_like_prefixes)
            or "/" not in model_name
        ):
            return self._openai_provider

        # LiteLLM fallback route
        return self._litellm_provider

    async def _execute_task(self, task: dict[str, Any]):
        """
        Required abstract method from the base CompletionProvider.
        We pick the sub-provider based on model name, then forward the async call.
        """
        generation_config: GenerationConfig = task["generation_config"]
        model_name = generation_config.model
        sub_provider = self._choose_subprovider_by_model(model_name)
        return await sub_provider._execute_task(task)

    def _execute_task_sync(self, task: dict[str, Any]):
        """
        Required abstract method from the base CompletionProvider.
        We pick the sub-provider based on model name, then forward the sync call.
        """
        generation_config: GenerationConfig = task["generation_config"]
        model_name = generation_config.model
        sub_provider = self._choose_subprovider_by_model(model_name)
        return sub_provider._execute_task_sync(task)
