import json

from hatchet_sdk import Context

from core.base.abstractions import Document, DocumentInfo

from ..services import IngestionService, IngestionServiceAdapter
from .base import r2r_hatchet


@r2r_hatchet.workflow(
    name="ingest-file", on_events=["file:ingest"], timeout=3600
)
class IngestFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def parse_file(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
            input_data
        )

        documents_and_info = await self.ingestion_service.ingest_file_ingress(
            **parsed_data
        )

        try:
            extractions = await self.ingestion_service.parse_file(
                documents_and_info["info"],
                documents_and_info["document"],
            )
            return {
                "result": extractions,
                "info": documents_and_info["info"].json(),
            }
        except Exception as e:
            raise ValueError(f"Failed to parse document extractions: {str(e)}")

    @r2r_hatchet.step(retries=3, parents=["parse_file"])
    async def chunk_document(self, context: Context) -> None:
        inputs = context.step_output("parse_file")
        document_info = DocumentInfo.from_dict(json.loads(inputs["info"]))
        chunking_config = context.workflow_input()["request"].get(
            "chunking_config"
        )
        chunks = await self.ingestion_service.chunk_document(
            document_info,
            [json.loads(extraction) for extraction in inputs["result"]],
            chunking_config,
        )
        return {"result": chunks}

    @r2r_hatchet.step(retries=3, parents=["chunk_document"])
    async def embed_and_store(self, context: Context) -> None:
        inputs = context.step_output("parse_file")
        document_info = DocumentInfo.from_dict(json.loads(inputs["info"]))

        chunks = context.step_output("chunk_document")["result"]
        embeddings = await self.ingestion_service.embed_document(
            document_info, [json.loads(chunk) for chunk in chunks]
        )
        await self.ingestion_service.store_embeddings(
            document_info, [json.loads(embedding) for embedding in embeddings]
        )
        return {}

    @r2r_hatchet.step(retries=3, parents=["embed_and_store"])
    async def finalize_ingestion(self, context: Context) -> None:
        inputs = context.step_output("parse_file")
        document_info = DocumentInfo.from_dict(json.loads(inputs["info"]))
        await self.ingestion_service.finalize_ingestion(document_info)
        
        return None


@r2r_hatchet.workflow(
    name="update-files", on_events=["file:update"], timeout=3600
)
class UpdateFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def update_files(self, context: Context) -> None:
        data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_update_files_input(data)

        await self.ingestion_service.update_files(**parsed_data)
