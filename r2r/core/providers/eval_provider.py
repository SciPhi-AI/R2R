from typing import Optional, Union

from .base_provider import Provider, ProviderConfig
from .llm_provider import GenerationConfig, LLMConfig


class EvalConfig(ProviderConfig):
    """A base eval config class"""

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
