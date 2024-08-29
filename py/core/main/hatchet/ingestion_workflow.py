import json

from hatchet_sdk import Context

from ..services import IngestionService, IngestionServiceAdapter
from .base import r2r_hatchet


@r2r_hatchet.workflow(
    name="ingest-file", on_events=["file:ingest"], timeout=3600
)
class IngestFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def parse_document_extractions(self, context: Context) -> None:
        data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_ingest_file_input(data)

        extractions = await self.ingestion_service.parse_document_extractions(
            **parsed_data
        )
        return {"result": extractions}

    @r2r_hatchet.step(retries=3, parents=["parse_document_extractions"])
    async def fragment_extractions(self, context: Context) -> None:
        extractions = context.step_output("parse_document_extractions")[
            "result"
        ]
        chunking_config = context.workflow_input()["request"].get(
            "chunking_config"
        )
        chunks = await self.ingestion_service.fragment_extractions(
            [json.loads(extraction) for extraction in extractions],
            chunking_config,
        )
        return {"result": chunks}

    @r2r_hatchet.step(retries=3, parents=["fragment_extractions"])
    async def embed_documents(self, context: Context) -> dict:
        chunked_documents = context.step_output("fragment_extractions")[
            "result"
        ]
        embeddings = await self.ingestion_service.embed_documents(
            [json.loads(chunk) for chunk in chunked_documents]
        )
        return {"result": embeddings}

    @r2r_hatchet.step(retries=3, parents=["embed_documents"])
    async def store_embeddings(self, context: Context) -> dict:
        embeddings = context.step_output("embed_documents")["result"]
        embeddings = await self.ingestion_service.store_embeddings(
            [json.loads(embedding) for embedding in embeddings]
        )
        return {"result": embeddings}


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
