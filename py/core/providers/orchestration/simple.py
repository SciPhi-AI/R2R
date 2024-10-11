from typing import Any

from core.base import OrchestrationConfig, OrchestrationProvider, Workflow


class SimpleOrchestrationProvider(OrchestrationProvider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.config = config
        self.messages: dict[str, str] = {}

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
            from core.main.orchestration.simple.kg_workflow import (
                simple_kg_factory,
            )

            self.kg_workflows = simple_kg_factory(service)

    async def run_workflow(
        self, workflow_name: str, parameters: dict, options: dict
    ) -> dict[str, str]:
        if workflow_name in self.ingestion_workflows:
            await self.ingestion_workflows[workflow_name](
                parameters.get("request")
            )
            return {"message": self.messages[workflow_name]}
        elif workflow_name in self.kg_workflows:
            await self.kg_workflows[workflow_name](parameters.get("request"))
            return {"message": self.messages[workflow_name]}
        else:
            raise ValueError(f"Workflow '{workflow_name}' not found.")
