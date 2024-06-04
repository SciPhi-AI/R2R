"""Base classes for language model providers."""

import logging
from abc import abstractmethod
from typing import Optional

from pydantic import BaseModel

from ..abstractions.llm import LLMChatCompletion, LLMChatCompletionChunk
from .base_provider import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class GenerationConfig(BaseModel):
    temperature: float = 0.1
    top_p: float = 1.0
    top_k: int = 100
    max_tokens_to_sample: int = 1_024
    model: str
    stream: bool = False
    functions: Optional[list[dict]] = None
    skip_special_tokens: bool = False
    stop_token: Optional[str] = None
    num_beams: int = 1
    do_sample: bool = True
    # Additional args to pass to the generation config
    generate_with_chat: bool = False
    add_generation_kwargs: Optional[dict] = {}
    api_base: Optional[str] = None


class LLMConfig(ProviderConfig):
    """A base LLM config class"""

    provider: Optional[str] = None

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("Provider must be set.")

        if self.provider and self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["litellm", "openai"]


class LLMProvider(Provider):
    """An abstract class to provide a common interface for LLMs."""

    def __init__(
        self,
        config: LLMConfig,
    ) -> None:
        if not isinstance(config, LLMConfig):
            raise ValueError(
                "LLMProvider must be initialized with a `LLMConfig`."
            )
        logger.info(f"Initializing LLM provider with config: {config}")

        super().__init__(config)

    @abstractmethod
    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        """Abstract method to get a chat completion from the provider."""
        pass

    @abstractmethod
    def get_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletionChunk:
        """Abstract method to get a completion stream from the provider."""
        pass
