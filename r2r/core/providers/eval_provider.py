import random
from abc import abstractmethod
from typing import Optional, Union

from .base_provider import Provider, ProviderConfig
from .llm_provider import LLMConfig


class EvalConfig(ProviderConfig):
    """A base eval config class"""

    sampling_fraction: float = 0.0
    llm: LLMConfig

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["local"]


class EvalProvider(Provider):
    """An abstract class to provide a common interface for evaluation providers."""

    def __init__(self, config: EvalConfig):
        if not isinstance(config, EvalConfig):
            raise ValueError(
                "EvalProvider must be initialized with a `EvalConfig`."
            )

        super().__init__(config)

    @abstractmethod
    def _evaluate(
        self, query: str, context: str, completion: str
    ) -> dict[str, dict[str, Union[str, float]]]:
        pass

    def evaluate(
        self, query: str, context: str, completion: str
    ) -> Optional[dict]:
        if random.random() < self.config.sampling_fraction:
            return self._evaluate(query, context, completion)
        return None
