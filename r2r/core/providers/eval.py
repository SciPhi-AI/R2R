import random
from typing import Optional


class EvalProvider:
    providers = ["deepeval", "parea"]

    def __init__(self, provider: str, sampling_fraction: float = 1.0):
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not supported.")
        self.provider = provider
        self.sampling_fraction = sampling_fraction

    def evaluate(
        self, query: str, context: str, completion: str
    ) -> Optional[dict]:
        if random.random() < self.sampling_fraction:
            return self.evaluate(query, context, completion)
        return None
