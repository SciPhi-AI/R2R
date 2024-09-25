import asyncio
from typing import Any, Callable, Optional

from hatchet_sdk import Hatchet

from core.base import OrchestrationConfig, OrchestrationProvider, Workflow


class HatchetOrchestrationProvider(OrchestrationProvider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.orchestrator = Hatchet()
        self.config: OrchestrationConfig = config  # for type hinting
        self.worker

    def workflow(self, *args, **kwargs) -> Callable:
        print("making workflow....")
        return self.orchestrator.workflow(*args, **kwargs)

    def step(self, *args, **kwargs) -> Callable:
        return self.orchestrator.step(*args, **kwargs)

    def on_failure_step(self, *args, **kwargs) -> Callable:
        return self.orchestrator.on_failure_step(*args, **kwargs)

    def get_worker(self, name: str, max_threads: Optional[int] = None) -> Any:
        if not max_threads:
            max_threads = self.config.max_threads
        self.worker = self.orchestrator.worker(name, max_threads)
        return self.worker

    async def start_worker(self):
        if not self.worker:
            raise ValueError(
                "Worker not initialized. Call get_worker() first."
            )

        asyncio.create_task(self.worker.async_start())

    def run_workflow(
        self,
        workflow_name: str,
        parameters: dict,
        options: dict,
        *args,
        **kwargs,
    ) -> Any:
        self.orchestrator.admin.run_workflow(
            workflow_name,
            parameters,
            options=options,
            *args,
            **kwargs,
        )

    def register_workflow(self, workflow: Workflow, service: Any) -> None:
        if workflow == Workflow.INGESTION:
            print("registering ingestion workflow.... , service = ", service)
            from core.main.orchestration.hatchet.ingestion_workflow import (
                hatchet_ingestion_workflow,
            )

            workflow = hatchet_ingestion_workflow(self, service)
            if self.worker:
                self.worker.register_workflow(workflow)

            print("done...")
        elif workflow == Workflow.RESTRUCTURE:
            from core.main.orchestration.hatchet.restructure_workflow import (
                hatchet_restructure_workflow,
            )

            x = hatchet_restructure_workflow(self, service)
        else:
            raise ValueError(f"Workflow {workflow} not supported.")
