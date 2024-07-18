from typing import Optional, Union

from ..abstractions.llm import GenerationConfig
from .base import Provider, ProviderConfig
from .llm import LLMConfig


class EvalConfig(ProviderConfig):
    """A base eval config class"""

    llm: Optional[LLMConfig] = None

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} not supported.")
        if self.provider and not self.llm:
            raise ValueError(
                "EvalConfig must have a `llm` attribute when specifying a provider."
            )

    @property
    def supported_providers(self) -> list[str]:
        return [None, "local"]


class EvalProvider(Provider):
    """An abstract class to provide a common interface for evaluation providers."""

    def __init__(self, config: EvalConfig):
        if not isinstance(config, EvalConfig):
            raise ValueError(
                "EvalProvider must be initialized with a `EvalConfig`."
            )

        super().__init__(config)

    def evaluate(
        self,
        query: str,
        context: str,
        completion: str,
        eval_generation_config: Optional[GenerationConfig] = None,
    ) -> dict[str, dict[str, Union[str, float]]]:
        return self._evaluate(
            query, context, completion, eval_generation_config
        )
