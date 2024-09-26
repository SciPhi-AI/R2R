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

        elif workflow == Workflow.RESTRUCTURE:
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

    # def register_workflows(
    #     self, workflow: Workflow, service: Any, messages: dict
    # ) -> None:
    #     if workflow == Workflow.INGESTION:
    #         from core.main.orchestration import simple_ingestion_factory

    #         ingestion_workflows = simple_ingestion_factory(service)

    #         def _run_ingest_files(input_data: dict):
    #             asyncio.run(ingestion_workflows["ingest-file"](input_data))
    #             return {"message": messages["ingest-file"]}

    #         def _run_update_files(input_data: dict):
    #             asyncio.run(ingestion_workflows["update-files"](input_data))
    #             return {"message": messages["update-file"]}

    #         self.ingest_files = _run_ingest_files
    #         self.update_files = _run_update_files

    #     elif workflow == Workflow.RESTRUCTURE:
    #         from core.main.orchestration.simple.restructure_workflow import simple_restructure_factory

    #         restructure_workflows = simple_restructure_factory(service)

    #         def _run_kg_extract_and_store(input_data: dict):
    #             asyncio.run(restructure_workflows["kg_extract_and_store"](input_data))
    #             return {"message": messages["kg_extract_and_store"]}

    #         def _create_graph(input_data: dict):
    #             asyncio.run(restructure_workflows["create_graph"](input_data))
    #             return {"message": messages["create_graph"]}

    #         def _enrich_graph(input_data: dict):
    #             asyncio.run(restructure_workflows["enrich_graph"](input_data))
    #             return {"message": messages["enrich_graph"]}

    #         def _kg_community_summary(input_data: dict):
    #             asyncio.run(restructure_workflows["kg_community_summary"](input_data))
    #             return {"message": messages["kg_community_summary"]}

    #         self.kg_extract_and_store = _run_kg_extract_and_store
    #         self.create_graph = _create_graph
    #         self.enrich_graph = _enrich_graph
    #         self.kg_community_summary = _kg_community_summary

    # def run_workflow(
    #     self, workflow_name: str, input: dict, options: dict
    # ) -> Any:
    #     if workflow_name == "ingest-file":
    #         return self.ingest_files(input.get("request"))
    #     elif workflow_name == "update-file":
    #         return self.update_files(input.get("request"))
