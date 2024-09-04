import asyncio
import json

from hatchet_sdk import Context

from core.base import increment_version
from core.base.abstractions import DocumentInfo, R2RException

from ..services import IngestionService, IngestionServiceAdapter
from .base import r2r_hatchet


@r2r_hatchet.workflow(name="ingest-file", timeout=3600)
class IngestFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def parse_file(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
            input_data
        )

        document_info = await self.ingestion_service.ingest_file_ingress(
            **parsed_data
        )

        try:
            extractions = await self.ingestion_service.parse_file(
                document_info["info"]
            )
            return {
                "result": extractions,
                "info": document_info["info"].model_dump_json(),
            }
        except Exception as e:
            raise ValueError(f"Failed to parse document extractions: {str(e)}")

    @r2r_hatchet.step(retries=3, parents=["parse_file"])
    async def chunk_document(self, context: Context) -> None:
        prev_step = context.step_output("parse_file")
        chunking_config = context.workflow_input()["request"].get(
            "chunking_config"
        )

        chunks = await self.ingestion_service.chunk_document(
            self.get_document_info(context),
            [json.loads(extraction) for extraction in prev_step["result"]],
            chunking_config,
        )
        return {"result": chunks}

    @r2r_hatchet.step(retries=3, parents=["chunk_document"])
    async def embed_and_store(self, context: Context) -> None:
        prev_step = context.step_output("chunk_document")
        document_info = self.get_document_info(context)

        embeddings = await self.ingestion_service.embed_document(
            document_info, [json.loads(chunk) for chunk in prev_step["result"]]
        )
        await self.ingestion_service.store_embeddings(
            document_info, [json.loads(embedding) for embedding in embeddings]
        )
        return {}

    @r2r_hatchet.step(retries=3, parents=["embed_and_store"])
    async def finalize_ingestion(self, context: Context) -> None:
        is_update = context.workflow_input()["request"].get("is_update")

        await self.ingestion_service.finalize_ingestion(
            self.get_document_info(context), is_update=is_update
        )

        return None

    def get_document_info(self, context: Context) -> DocumentInfo:
        return DocumentInfo.from_dict(
            json.loads(context.step_output("parse_file")["info"])
        )


# TODO: Implement a check to see if the file is actually changed before updating
@r2r_hatchet.workflow(name="update-files", timeout=3600)
class UpdateFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def update_files(self, context: Context) -> None:
        data = context.workflow_input()["request"]
        print(f"Data is {data} and type is {type(data)}")
        parsed_data = IngestionServiceAdapter.parse_update_files_input(data)

        file_datas = parsed_data["file_datas"]
        user = parsed_data["user"]
        document_ids = parsed_data["document_ids"]
        metadatas = parsed_data["metadatas"]
        chunking_config = parsed_data["chunking_config"]

        if not file_datas:
            raise R2RException(
                status_code=400, message="No files provided for update."
            )
        if len(document_ids) != len(file_datas):
            raise R2RException(
                status_code=400,
                message="Number of ids does not match number of files.",
            )

        documents_overview = self.ingestion_service.providers.database.relational.get_documents_overview(
            filter_document_ids=document_ids,
            filter_user_ids=None if user.is_superuser else [user.id],
        )

        if len(documents_overview) != len(document_ids):
            raise R2RException(
                status_code=404,
                message="One or more documents not found.",
            )

        results = []

        for idx, (file_data, doc_id, doc_info) in enumerate(
            zip(file_datas, document_ids, documents_overview)
        ):
            new_version = increment_version(doc_info.version)

            updated_metadata = (
                metadatas[idx] if metadatas else doc_info.metadata
            )
            updated_metadata["title"] = (
                updated_metadata.get("title")
                or file_data["filename"].split("/")[-1]
            )

            # Prepare input for ingest_file workflow
            ingest_input = {
                "file_data": file_data,
                "user": data.get("user"),
                "metadata": updated_metadata,
                "document_id": str(doc_id),
                "version": new_version,
                "chunking_config": (
                    chunking_config.model_dump_json()
                    if chunking_config
                    else None
                ),
                "is_update": True,
            }

            # Spawn ingest_file workflow as a child workflow
            child_result = (
                await context.aio.spawn_workflow(
                    "ingest-file",
                    {"request": ingest_input},
                    key=f"ingest_file_{doc_id}",
                )
            ).result()
            results.append(child_result)

        await asyncio.gather(*results)

        return None
