import random
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union

from .base import Provider, ProviderConfig


@dataclass
class EvalConfig(ProviderConfig):
    """A base eval config class"""

    provider: Optional[str] = None
    sampling_fraction: float = 1.0

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} not supported.")
        if self.provider == "none" and self.sampling_fraction != 0.0:
            raise ValueError(
                f"Sampling fraction must be 0.0 when setting evaluation provider to None."
            )

    @property
    def supported_providers(self) -> List[str]:
        return ["deepeval", "parea", "none"]


class EvalProvider(Provider):
    """An abstract class to provide a common interface for evaluation providers."""

    def __init__(self, config: EvalConfig):
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
