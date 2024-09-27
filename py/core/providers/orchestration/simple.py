import asyncio
from typing import Any

from core.base import OrchestrationConfig, OrchestrationProvider, Workflow


class SimpleOrchestrationProvider(OrchestrationProvider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.config = config
        self.messages = {}

    async def start_worker(self):
        pass

    def get_worker(self, name: str, max_threads: int) -> Any:
        pass

    def step(self, *args, **kwargs) -> Any:
        pass

    def workflow(self, *args, **kwargs) -> Any:
        pass

    def failure(self, *args, **kwargs) -> Any:
        pass

    def register_workflows(
        self, workflow: Workflow, service: Any, messages: dict
    ) -> None:
        for key, msg in messages.items():
            self.messages[key] = msg

        if workflow == Workflow.INGESTION:
            from core.main.orchestration import simple_ingestion_factory

            self.ingestion_workflows = simple_ingestion_factory(service)

        elif workflow == Workflow.KG:
            from core.main.orchestration.simple.restructure_workflow import (
                simple_restructure_factory,
            )

            self.restructure_workflows = simple_restructure_factory(service)

    def run_workflow(
        self, workflow_name: str, input: dict, options: dict
    ) -> Any:
        if workflow_name in self.ingestion_workflows:
            asyncio.run(
                self.ingestion_workflows[workflow_name](input.get("request"))
            )
            return {"message": self.messages[workflow_name]}
        elif workflow_name in self.restructure_workflows:
            asyncio.run(
                self.restructure_workflows[workflow_name](input.get("request"))
            )
            return {"message": self.messages[workflow_name]}
        else:
            raise ValueError(f"Workflow '{workflow_name}' not found.")
