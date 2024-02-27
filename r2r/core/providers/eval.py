import abc
from typing import Optional
import random

class EvalProvider:
    providers = ["deepeval"]
    def __init__(self, provider: str, sampling_fraction: float = 1.0):
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not supported.")
        self.provider = provider
        self.sampling_fraction = sampling_fraction
    
    def evaluate(self, query: str, context: str, completion: str) -> Optional[dict]:
        if random.random() < self.sampling_fraction:
            if self.provider == "deepeval":
                return self._deepeval_evaluate(query, context, completion)
        return None
