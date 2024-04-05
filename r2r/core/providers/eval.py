import random
from abc import ABC, abstractmethod
from typing import Optional, Union


class EvalProvider(ABC):
    providers = ["deepeval", "parea", "none"]

    def __init__(self, provider: str, sampling_fraction: float = 1.0):
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not supported.")
        if provider == "none" and sampling_fraction != 0.0:
            raise ValueError(
                f"Sampling fraction must be 0.0 when setting evaluation provider to None."
            )

        self.provider = provider
        self.sampling_fraction = sampling_fraction

    def evaluate(
        self, query: str, context: str, completion: str
    ) -> Optional[dict]:
        if random.random() < self.sampling_fraction:
            return self._evaluate(query, context, completion)
        return None

    @abstractmethod
    def _evaluate(
        self, query: str, context: str, completion: str
    ) -> dict[str, dict[str, Union[str, float]]]:
        pass
