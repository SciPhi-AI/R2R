import asyncio
import logging

from hatchet_sdk import Context

from core.base import IngestionStatus, increment_version
from core.base.abstractions import DocumentInfo, R2RException

from ..services import IngestionService, IngestionServiceAdapter
from .base import r2r_hatchet

logger = logging.getLogger(__name__)


@r2r_hatchet.workflow(
    name="ingest-file",
    timeout="60m",
)
class IngestFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(timeout="60m")
    async def parse(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
            input_data
        )

        ingestion_result = await self.ingestion_service.ingest_file_ingress(
            **parsed_data
        )

        document_info = ingestion_result["info"]

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.PARSING,
        )

        return {
            "status": "Successfully parsed file",
            "document_info": document_info.to_dict(),
        }

    @r2r_hatchet.step(parents=["parse"], timeout="60m")
    async def extract(self, context: Context) -> dict:
        document_info_dict = context.step_output("parse")["document_info"]
        document_info = DocumentInfo(**document_info_dict)

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.EXTRACTING,
        )

        extractions_generator = await self.ingestion_service.parse_file(
            document_info
        )

        extractions = []
        async for extraction in extractions_generator:
            extractions.append(extraction)

        serializable_extractions = [
            fragment.to_dict() for fragment in extractions
        ]

        return {
            "status": "Successfully extracted data",
            "extractions": serializable_extractions,
            "document_info": document_info.to_dict(),
        }

    @r2r_hatchet.step(parents=["extract"], timeout="60m")
    async def chunk(self, context: Context) -> dict:
        document_info_dict = context.step_output("extract")["document_info"]
        document_info = DocumentInfo(**document_info_dict)

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.CHUNKING,
        )

        extractions = context.step_output("extract")["extractions"]
        chunking_config = context.workflow_input()["request"].get(
            "chunking_config"
        )

        chunk_generator = await self.ingestion_service.chunk_document(
            extractions,
            chunking_config,
        )

        chunks = []
        async for chunk in chunk_generator:
            chunks.append(chunk)

        serializable_chunks = [chunk.to_dict() for chunk in chunks]

        return {
            "status": "Successfully chunked data",
            "chunks": serializable_chunks,
            "document_info": document_info.to_dict(),
        }

    @r2r_hatchet.step(parents=["chunk"], timeout="60m")
    async def embed(self, context: Context) -> dict:
        document_info_dict = context.step_output("chunk")["document_info"]
        document_info = DocumentInfo(**document_info_dict)

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.EMBEDDING,
        )

        chunks = context.step_output("chunk")["chunks"]

        embedding_generator = await self.ingestion_service.embed_document(
            chunks
        )

        embeddings = []
        async for embedding in embedding_generator:
            embeddings.append(embedding)

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.STORING,
        )

        storage_generator = await self.ingestion_service.store_embeddings(
            embeddings
        )

        async for _ in storage_generator:
            pass

        return {
            "document_info": document_info.to_dict(),
        }

    @r2r_hatchet.step(parents=["embed"], timeout="60m")
    async def finalize(self, context: Context) -> dict:
        document_info_dict = context.step_output("embed")["document_info"]
        document_info = DocumentInfo(**document_info_dict)

        is_update = context.workflow_input()["request"].get("is_update")

        await self.ingestion_service.finalize_ingestion(
            document_info, is_update=is_update
        )

        await self.ingestion_service.update_document_status(
            document_info,
            status=IngestionStatus.SUCCESS,
        )

        return {
            "status": "Successfully finalized ingestion",
            "document_info": document_info.to_dict(),
        }

    @r2r_hatchet.on_failure_step()
    async def on_failure(self, context: Context) -> None:
        request = context.workflow_input().get("request", {})
        document_id = request.get("document_id")

        if not document_id:
            logger.error(
                "No document id was found in workflow input to mark a failure."
            )
            return

        try:
            documents_overview = await self.ingestion_service.providers.database.relational.get_documents_overview(
                filter_document_ids=[document_id]
            )

            if not documents_overview:
                logger.error(
                    f"Document with id {document_id} not found in database to mark failure."
                )
                return

            document_info = documents_overview[0]

            # Update the document status to FAILURE
            await self.ingestion_service.update_document_status(
                document_info,
                status=IngestionStatus.FAILURE,
            )

        except Exception as e:
            logger.error(
                f"Failed to update document status for {document_id}: {e}"
            )


# TODO: Implement a check to see if the file is actually changed before updating
@r2r_hatchet.workflow(name="update-files", timeout="60m")
class UpdateFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=0, timeout="60m")
    async def update_files(self, context: Context) -> None:
        data = context.workflow_input()["request"]
        parsed_data = IngestionServiceAdapter.parse_update_files_input(data)

        file_datas = parsed_data["file_datas"]
        user = parsed_data["user"]
        document_ids = parsed_data["document_ids"]
        metadatas = parsed_data["metadatas"]
        chunking_config = parsed_data["chunking_config"]
        file_sizes_in_bytes = parsed_data["file_sizes_in_bytes"]

        if not file_datas:
            raise R2RException(
                status_code=400, message="No files provided for update."
            )
        if len(document_ids) != len(file_datas):
            raise R2RException(
                status_code=400,
                message="Number of ids does not match number of files.",
            )

        documents_overview = await self.ingestion_service.providers.database.relational.get_documents_overview(
            filter_document_ids=document_ids,
            filter_user_ids=None if user.is_superuser else [user.id],
        )

        if len(documents_overview) != len(document_ids):
            raise R2RException(
                status_code=404,
                message="One or more documents not found.",
            )

        results = []

        for idx, (
            file_data,
            doc_id,
            doc_info,
            file_size_in_bytes,
        ) in enumerate(
            zip(
                file_datas,
                document_ids,
                documents_overview,
                file_sizes_in_bytes,
            )
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
                "size_in_bytes": file_size_in_bytes,
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
