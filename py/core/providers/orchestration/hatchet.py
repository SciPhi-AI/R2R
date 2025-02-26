# FIXME: Once the Hatchet workflows are type annotated, remove the type: ignore comments
import asyncio
import logging
from typing import Any, Callable, Optional

from core.base import OrchestrationConfig, OrchestrationProvider, Workflow

logger = logging.getLogger()


class HatchetOrchestrationProvider(OrchestrationProvider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        try:
            from hatchet_sdk import ClientConfig, Hatchet
        except ImportError:
            raise ImportError(
                "Hatchet SDK not installed. Please install it using `pip install hatchet-sdk`."
            ) from None
        root_logger = logging.getLogger()

        self.orchestrator = Hatchet(
            config=ClientConfig(
                logger=root_logger,
            ),
        )
        self.root_logger = root_logger
        self.config: OrchestrationConfig = config
        self.messages: dict[str, str] = {}

    def workflow(self, *args, **kwargs) -> Callable:
        return self.orchestrator.workflow(*args, **kwargs)

    def step(self, *args, **kwargs) -> Callable:
        return self.orchestrator.step(*args, **kwargs)

    def failure(self, *args, **kwargs) -> Callable:
        return self.orchestrator.on_failure_step(*args, **kwargs)

    def get_worker(self, name: str, max_runs: Optional[int] = None) -> Any:
        if not max_runs:
            max_runs = self.config.max_runs
        self.worker = self.orchestrator.worker(name, max_runs)  # type: ignore
        return self.worker

    def concurrency(self, *args, **kwargs) -> Callable:
        return self.orchestrator.concurrency(*args, **kwargs)

    async def start_worker(self):
        if not self.worker:
            raise ValueError(
                "Worker not initialized. Call get_worker() first."
            )

        asyncio.create_task(self.worker.async_start())

    async def run_workflow(
        self,
        workflow_name: str,
        parameters: dict,
        options: dict,
        *args,
        **kwargs,
    ) -> Any:
        task_id = self.orchestrator.admin.run_workflow(  # type: ignore
            workflow_name,
            parameters,
            options=options,  # type: ignore
            *args,
            **kwargs,
        )
        return {
            "task_id": str(task_id),
            "message": self.messages.get(
                workflow_name, "Workflow queued successfully."
            ),  # Return message based on workflow name
        }

    def register_workflows(
        self, workflow: Workflow, service: Any, messages: dict
    ) -> None:
        self.messages.update(messages)

        logger.info(
            f"Registering workflows for {workflow} with messages {messages}."
        )
        if workflow == Workflow.INGESTION:
            from core.main.orchestration.hatchet.ingestion_workflow import (  # type: ignore
                hatchet_ingestion_factory,
            )

            workflows = hatchet_ingestion_factory(self, service)
            if self.worker:
                for workflow in workflows.values():
                    self.worker.register_workflow(workflow)

        elif workflow == Workflow.GRAPH:
            from core.main.orchestration.hatchet.graph_workflow import (  # type: ignore
                hatchet_graph_search_results_factory,
            )

            workflows = hatchet_graph_search_results_factory(self, service)
            if self.worker:
                for workflow in workflows.values():
                    self.worker.register_workflow(workflow)
