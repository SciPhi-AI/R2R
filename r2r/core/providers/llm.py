"""Base classes for language model providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .base import Provider, ProviderConfig


@dataclass
class GenerationConfig(ABC):
    temperature: float = 0.1
    top_p: float = 1.0
    top_k: int = 100
    max_tokens_to_sample: int = 1_024
    model: Optional[str] = None
    stream: bool = False
    functions: Optional[list[dict]] = None
    skip_special_tokens: bool = False
    stop_token: Optional[str] = None
    num_beams: int = 1
    do_sample: bool = True
    # Additional args to pass to the generation config
    add_generation_kwargs: dict = field(default_factory=dict)
    generate_with_chat: bool = False
    api_base: Optional[str] = None


@dataclass
class LLMConfig(ProviderConfig):
    """A base LLM config class"""

    provider: Optional[str] = None

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("Provider must be set.")

        if self.provider and self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> List[str]:
        return ["litellm", "llama-cpp", "openai"]


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

        super().__init__(config)

    @abstractmethod
    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> ChatCompletion:
        """Abstract method to get a chat completion from the provider."""
        pass

    @abstractmethod
    def get_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> ChatCompletionChunk:
        """Abstract method to get a completion stream from the provider."""
        pass
