import asyncio
from typing import Any

from core.base import OrchestrationConfig, OrchestrationProvider, Workflow


class SimpleOrchestrationProvider(OrchestrationProvider):
    def __init__(self, config: OrchestrationConfig):
        super().__init__(config)
        self.config = config

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

    def register_workflows(self, workflow: Workflow, service: Any) -> None:
        if workflow == Workflow.INGESTION:

            def run_ingestion_workflow(input_data: dict):
                asyncio.run(
                    SimpleOrchestrationProvider.run_ingestion_workflow(
                        service, input_data
                    )
                )

            self.run_ingestion_workflow = run_ingestion_workflow

    def run_workflow(
        self, workflow_name: str, input: dict, options: dict
    ) -> Any:
        if workflow_name == "ingest-file":
            self.run_ingestion_workflow(input.get("request"))

    @staticmethod
    async def run_ingestion_workflow(service, input_data: dict):
        from core.base import IngestionStatus
        from core.main import IngestionServiceAdapter

        parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
            input_data
        )
        ingestion_result = await service.ingest_file_ingress(**parsed_data)
        document_info = ingestion_result["info"]

        await service.update_document_status(
            document_info, status=IngestionStatus.PARSING
        )
        extractions_generator = await service.parse_file(document_info)
        extractions = [
            extraction.model_dump()
            async for extraction in extractions_generator
        ]

        await service.update_document_status(
            document_info, status=IngestionStatus.CHUNKING
        )
        chunking_config = input_data.get("chunking_config")
        chunk_generator = await service.chunk_document(
            extractions, chunking_config
        )
        chunks = [chunk.model_dump() async for chunk in chunk_generator]

        await service.update_document_status(
            document_info, status=IngestionStatus.EMBEDDING
        )
        embedding_generator = await service.embed_document(chunks)
        embeddings = [
            embedding.model_dump() async for embedding in embedding_generator
        ]

        await service.update_document_status(
            document_info, status=IngestionStatus.STORING
        )
        storage_generator = await service.store_embeddings(embeddings)
        async for _ in storage_generator:
            pass

        is_update = input_data.get("is_update")
        await service.finalize_ingestion(document_info, is_update=is_update)

        await service.update_document_status(
            document_info, status=IngestionStatus.SUCCESS
        )
