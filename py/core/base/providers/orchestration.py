from abc import abstractmethod
from enum import Enum
from typing import Any

from .base import Provider, ProviderConfig


class Workflow(Enum):
    INGESTION = "ingestion"
    GRAPH = "graph"


class OrchestrationConfig(ProviderConfig):
    provider: str
    max_runs: int = 2_048
    graph_search_results_creation_concurrency_limit: int = 32
    ingestion_concurrency_limit: int = 16
    graph_search_results_concurrency_limit: int = 8

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider {self.provider} is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["hatchet", "simple"]


class OrchestrationProvider(Provider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.config = config
        self.worker = None

    @abstractmethod
    async def start_worker(self):
        pass

    @abstractmethod
    def get_worker(self, name: str, max_runs: int) -> Any:
        pass

    @abstractmethod
    def step(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def workflow(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def failure(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def register_workflows(
        self, workflow: Workflow, service: Any, messages: dict
    ) -> None:
        pass

    @abstractmethod
    async def run_workflow(
        self,
        workflow_name: str,
        parameters: dict,
        options: dict,
        *args,
        **kwargs,
    ) -> dict[str, str]:
        pass
