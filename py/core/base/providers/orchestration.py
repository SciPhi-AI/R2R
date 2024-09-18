from abc import abstractmethod
from typing import Any, Callable

from .base import Provider, ProviderConfig


class OrchestrationConfig(ProviderConfig):
    provider: str
    max_threads: int = 256

    def validate(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["hatchet"]


class OrchestrationProvider(Provider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.config = config
        self.worker = None

    @abstractmethod
    def register_workflow(self, workflow: Any) -> None:
        pass

    @abstractmethod
    def get_worker(self, name: str, max_threads: int) -> Any:
        pass

    @abstractmethod
    def workflow(self, *args, **kwargs) -> Callable:
        pass

    @abstractmethod
    def step(self, *args, **kwargs) -> Callable:
        pass

    @abstractmethod
    def start_worker(self):
        pass
