import asyncio
import logging
import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from hatchet_sdk import ConcurrencyLimitStrategy, Context
from litellm import AuthenticationError

from core.base import (
    DocumentChunk,
    IngestionStatus,
    KGEnrichmentStatus,
    OrchestrationProvider,
    generate_extraction_id,
    increment_version,
)
from core.base.abstractions import DocumentResponse, R2RException
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from ...services import IngestionService, IngestionServiceAdapter

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet

logger = logging.getLogger()


def hatchet_ingestion_factory(
    orchestration_provider: OrchestrationProvider, service: IngestionService
) -> dict[str, "Hatchet.Workflow"]:
    @orchestration_provider.workflow(
        name="ingest-files",
        timeout="60m",
    )
    class HatchetIngestFilesWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.concurrency(  # type: ignore
            max_runs=orchestration_provider.config.ingestion_concurrency_limit,  # type: ignore
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context: Context) -> str:
            # TODO: Possible bug in hatchet, the job can't find context.workflow_input() when rerun
            try:
                input_data = context.workflow_input()["request"]
                parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
                    input_data
                )
                return str(parsed_data["user"].id)
            except Exception as e:
                return str(uuid.uuid4())

        @orchestration_provider.step(retries=0, timeout="60m")
        async def parse(self, context: Context) -> dict:
            try:
                logger.info("Initiating ingestion workflow, step: parse")
                input_data = context.workflow_input()["request"]
                parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
                    input_data
                )

                ingestion_result = (
                    await self.ingestion_service.ingest_file_ingress(
                        **parsed_data
                    )
                )

                document_info = ingestion_result["info"]

                await self.ingestion_service.update_document_status(
                    document_info,
                    status=IngestionStatus.PARSING,
                )

                ingestion_config = parsed_data["ingestion_config"] or {}
                extractions_generator = (
                    await self.ingestion_service.parse_file(
                        document_info, ingestion_config
                    )
                )

                extractions = []
                async for extraction in extractions_generator:
                    extractions.append(extraction)

                await service.update_document_status(
                    document_info, status=IngestionStatus.AUGMENTING
                )
                await service.augment_document_info(
                    document_info,
                    [extraction.to_dict() for extraction in extractions],
                )

                await self.ingestion_service.update_document_status(
                    document_info,
                    status=IngestionStatus.EMBEDDING,
                )

                # extractions = context.step_output("parse")["extractions"]

                embedding_generator = (
                    await self.ingestion_service.embed_document(
                        [extraction.to_dict() for extraction in extractions]
                    )
                )

                embeddings = []
                async for embedding in embedding_generator:
                    embeddings.append(embedding)

                await self.ingestion_service.update_document_status(
                    document_info,
                    status=IngestionStatus.STORING,
                )

                storage_generator = await self.ingestion_service.store_embeddings(  # type: ignore
                    embeddings
                )

                async for _ in storage_generator:
                    pass

                is_update = context.workflow_input()["request"].get(
                    "is_update"
                )

                await self.ingestion_service.finalize_ingestion(
                    document_info, is_update=is_update
                )

                await self.ingestion_service.update_document_status(
                    document_info,
                    status=IngestionStatus.SUCCESS,
                )

                collection_ids = context.workflow_input()["request"].get(
                    "collection_ids"
                )
                if not collection_ids:
                    # TODO: Move logic onto the `management service`
                    collection_id = generate_default_user_collection_id(
                        document_info.owner_id
                    )
                    await service.providers.database.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.assign_document_to_collection_vector(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.set_workflow_status(
                        id=collection_id,
                        status_type="graph_sync_status",
                        status=KGEnrichmentStatus.OUTDATED,
                    )
                    await service.providers.database.set_workflow_status(
                        id=collection_id,
                        status_type="graph_cluster_status",  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                        status=KGEnrichmentStatus.OUTDATED,
                    )
                else:
                    for collection_id_str in collection_ids:
                        collection_id = UUID(collection_id_str)
                        try:
                            name = document_info.title or "N/A"
                            description = ""
                            result = await self.providers.database.create_collection(
                                owner_id=document_info.owner_id,
                                name=name,
                                description=description,
                                collection_id=collection_id,
                            )
                            await self.providers.database.graph_handler.create(
                                collection_id=collection_id,
                                name=name,
                                description=description,
                                graph_id=collection_id,
                            )

                        except Exception as e:
                            logger.warning(
                                f"Warning, could not create collection with error: {str(e)}"
                            )

                        await service.providers.database.assign_document_to_collection_relational(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.assign_document_to_collection_vector(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.set_workflow_status(
                            id=collection_id,
                            status_type="graph_sync_status",
                            status=KGEnrichmentStatus.OUTDATED,
                        )
                        await service.providers.database.set_workflow_status(
                            id=collection_id,
                            status_type="graph_cluster_status",  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                            status=KGEnrichmentStatus.OUTDATED,
                        )
                # get server chunk enrichment settings and override parts of it if provided in the ingestion config
                server_chunk_enrichment_settings = getattr(
                    service.providers.ingestion.config,
                    "chunk_enrichment_settings",
                    None,
                )

                if server_chunk_enrichment_settings:
                    chunk_enrichment_settings = update_settings_from_dict(
                        server_chunk_enrichment_settings,
                        ingestion_config.get("chunk_enrichment_settings", {})
                        or {},
                    )

                if chunk_enrichment_settings.enable_chunk_enrichment:

                    logger.info("Enriching document with contextual chunks")

                    # TODO: the status updating doesn't work because document_info doesn't contain information about collection IDs
                    # we don't update the document_info when we assign document_to_collection_relational and document_to_collection_vector
                    # hack: get document_info again from DB
                    document_info = (
                        await self.ingestion_service.providers.database.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                            offset=0,
                            limit=100,
                            filter_user_ids=[document_info.user_id],
                            filter_document_ids=[document_info.id],
                        )
                    )["results"][0]

                    await self.ingestion_service.update_document_status(
                        document_info,
                        status=IngestionStatus.ENRICHING,
                    )

                    await self.ingestion_service.chunk_enrichment(
                        document_id=document_info.id,
                        chunk_enrichment_settings=chunk_enrichment_settings,
                    )

                    await self.ingestion_service.update_document_status(
                        document_info,
                        status=IngestionStatus.ENRICHED,
                    )

                return {
                    "status": "Successfully finalized ingestion",
                    "document_info": document_info.to_dict(),
                }

            except AuthenticationError as e:
                raise R2RException(
                    status_code=401,
                    message="Authentication error: Invalid API key or credentials.",
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error during ingestion: {str(e)}",
                )

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            request = context.workflow_input().get("request", {})
            document_id = request.get("document_id")

            if not document_id:
                logger.error(
                    "No document id was found in workflow input to mark a failure."
                )
                return

            try:
                documents_overview = (
                    await self.ingestion_service.providers.database.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                        offset=0,
                        limit=100,
                        filter_document_ids=[document_id],
                    )
                )["results"]

                if not documents_overview:
                    logger.error(
                        f"Document with id {document_id} not found in database to mark failure."
                    )
                    return

                document_info = documents_overview[0]

                # Update the document status to FAILED
                if document_info.ingestion_status not in [
                    IngestionStatus.SUCCESS,
                    IngestionStatus.ENRICHED,
                ]:
                    await self.ingestion_service.update_document_status(
                        document_info,
                        status=IngestionStatus.FAILED,
                    )

            except Exception as e:
                logger.error(
                    f"Failed to update document status for {document_id}: {e}"
                )

    # TODO: Implement a check to see if the file is actually changed before updating
    @orchestration_provider.workflow(name="update-files", timeout="60m")
    class HatchetUpdateFilesWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(retries=0, timeout="60m")
        async def update_files(self, context: Context) -> None:
            data = context.workflow_input()["request"]
            parsed_data = IngestionServiceAdapter.parse_update_files_input(
                data
            )

            file_datas = parsed_data["file_datas"]
            user = parsed_data["user"]
            document_ids = parsed_data["document_ids"]
            metadatas = parsed_data["metadatas"]
            ingestion_config = parsed_data["ingestion_config"]
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

            documents_overview = (
                await self.ingestion_service.providers.database.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                    offset=0,
                    limit=100,
                    filter_document_ids=document_ids,
                    filter_user_ids=None if user.is_superuser else [user.id],
                )
            )["results"]

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
                    "ingestion_config": (
                        ingestion_config.model_dump_json()
                        if ingestion_config
                        else None
                    ),
                    "size_in_bytes": file_size_in_bytes,
                    "is_update": True,
                }

                # Spawn ingest_file workflow as a child workflow
                child_result = (
                    await context.aio.spawn_workflow(
                        "ingest-files",
                        {"request": ingest_input},
                        key=f"ingest_file_{doc_id}",
                    )
                ).result()
                results.append(child_result)

            await asyncio.gather(*results)

            return None

    @orchestration_provider.workflow(
        name="ingest-chunks",
        timeout="60m",
    )
    class HatchetIngestChunksWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(timeout="60m")
        async def ingest(self, context: Context) -> dict:
            input_data = context.workflow_input()["request"]
            parsed_data = IngestionServiceAdapter.parse_ingest_chunks_input(
                input_data
            )

            document_info = await self.ingestion_service.ingest_chunks_ingress(
                **parsed_data
            )

            await self.ingestion_service.update_document_status(
                document_info, status=IngestionStatus.EMBEDDING
            )
            document_id = document_info.id

            extractions = [
                DocumentChunk(
                    id=generate_extraction_id(document_id, i),
                    document_id=document_id,
                    collection_ids=[],
                    owner_id=document_info.owner_id,
                    data=chunk.text,
                    metadata=parsed_data["metadata"],
                ).to_dict()
                for i, chunk in enumerate(parsed_data["chunks"])
            ]
            return {
                "status": "Successfully ingested chunks",
                "extractions": extractions,
                "document_info": document_info.to_dict(),
            }

        @orchestration_provider.step(parents=["ingest"], timeout="60m")
        async def embed(self, context: Context) -> dict:
            document_info_dict = context.step_output("ingest")["document_info"]
            document_info = DocumentResponse(**document_info_dict)

            extractions = context.step_output("ingest")["extractions"]

            embedding_generator = await self.ingestion_service.embed_document(
                extractions
            )
            embeddings = [
                embedding.model_dump()
                async for embedding in embedding_generator
            ]

            await self.ingestion_service.update_document_status(
                document_info, status=IngestionStatus.STORING
            )

            storage_generator = await self.ingestion_service.store_embeddings(
                embeddings
            )
            async for _ in storage_generator:
                pass

            return {
                "status": "Successfully embedded and stored chunks",
                "document_info": document_info.to_dict(),
            }

        @orchestration_provider.step(parents=["embed"], timeout="60m")
        async def finalize(self, context: Context) -> dict:
            document_info_dict = context.step_output("embed")["document_info"]
            document_info = DocumentResponse(**document_info_dict)

            await self.ingestion_service.finalize_ingestion(
                document_info, is_update=False
            )

            await self.ingestion_service.update_document_status(
                document_info, status=IngestionStatus.SUCCESS
            )

            try:
                # TODO - Move logic onto the `management service`
                collection_ids = context.workflow_input()["request"].get(
                    "collection_ids"
                )
                if not collection_ids:
                    # TODO: Move logic onto the `management service`
                    collection_id = generate_default_user_collection_id(
                        document_info.owner_id
                    )
                    await service.providers.database.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.assign_document_to_collection_vector(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.set_workflow_status(
                        id=collection_id,
                        status_type="graph_sync_status",
                        status=KGEnrichmentStatus.OUTDATED,
                    )
                    await service.providers.database.set_workflow_status(
                        id=collection_id,
                        status_type="graph_cluster_status",  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                        status=KGEnrichmentStatus.OUTDATED,
                    )
                else:
                    for collection_id_str in collection_ids:
                        collection_id = UUID(collection_id_str)
                        try:
                            name = document_info.title or "N/A"
                            description = ""
                            await service.providers.database.create_collection(
                                owner_id=document_info.owner_id,
                                name=name,
                                description=description,
                                collection_id=collection_id,
                            )
                            await self.providers.database.graph_handler.create(
                                collection_id=collection_id,
                                name=name,
                                description=description,
                                graph_id=collection_id,
                            )

                        except Exception as e:
                            logger.warning(
                                f"Warning, could not create collection with error: {str(e)}"
                            )

                        await service.providers.database.assign_document_to_collection_relational(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.assign_document_to_collection_vector(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.set_workflow_status(
                            id=collection_id,
                            status_type="graph_sync_status",
                            status=KGEnrichmentStatus.OUTDATED,
                        )
                        await service.providers.database.set_workflow_status(
                            id=collection_id,
                            status_type="graph_cluster_status",
                            status=KGEnrichmentStatus.OUTDATED,  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                        )
            except Exception as e:
                logger.error(
                    f"Error during assigning document to collection: {str(e)}"
                )

            return {
                "status": "Successfully finalized ingestion",
                "document_info": document_info.to_dict(),
            }

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            request = context.workflow_input().get("request", {})
            document_id = request.get("document_id")

            if not document_id:
                logger.error(
                    "No document id was found in workflow input to mark a failure."
                )
                return

            try:
                documents_overview = (
                    await self.ingestion_service.providers.database.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                        offset=0,
                        limit=100,
                        filter_document_ids=[document_id],
                    )
                )["results"]

                if not documents_overview:
                    logger.error(
                        f"Document with id {document_id} not found in database to mark failure."
                    )
                    return

                document_info = documents_overview[0]

                if (
                    not document_info.ingestion_status
                    == IngestionStatus.SUCCESS
                ):
                    await self.ingestion_service.update_document_status(
                        document_info, status=IngestionStatus.FAILED
                    )

            except Exception as e:
                logger.error(
                    f"Failed to update document status for {document_id}: {e}"
                )

    @orchestration_provider.workflow(
        name="update-chunk",
        timeout="60m",
    )
    class HatchetUpdateChunkWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(timeout="60m")
        async def update_chunk(self, context: Context) -> dict:
            try:
                input_data = context.workflow_input()["request"]
                parsed_data = IngestionServiceAdapter.parse_update_chunk_input(
                    input_data
                )

                document_uuid = (
                    UUID(parsed_data["document_id"])
                    if isinstance(parsed_data["document_id"], str)
                    else parsed_data["document_id"]
                )
                extraction_uuid = (
                    UUID(parsed_data["id"])
                    if isinstance(parsed_data["id"], str)
                    else parsed_data["id"]
                )

                await self.ingestion_service.update_chunk_ingress(
                    document_id=document_uuid,
                    chunk_id=extraction_uuid,
                    text=parsed_data.get("text"),
                    user=parsed_data["user"],
                    metadata=parsed_data.get("metadata"),
                    collection_ids=parsed_data.get("collection_ids"),
                )

                return {
                    "message": "Chunk update completed successfully.",
                    "task_id": context.workflow_run_id(),
                    "document_ids": [str(document_uuid)],
                }

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error during chunk update: {str(e)}",
                )

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            # Handle failure case if necessary
            pass

    @orchestration_provider.workflow(
        name="create-vector-index", timeout="360m"
    )
    class HatchetCreateVectorIndexWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(timeout="60m")
        async def create_vector_index(self, context: Context) -> dict:
            input_data = context.workflow_input()["request"]
            parsed_data = (
                IngestionServiceAdapter.parse_create_vector_index_input(
                    input_data
                )
            )

            await self.ingestion_service.providers.database.create_index(
                **parsed_data
            )

            return {
                "status": "Vector index creation queued successfully.",
            }

    @orchestration_provider.workflow(name="delete-vector-index", timeout="30m")
    class HatchetDeleteVectorIndexWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(timeout="10m")
        async def delete_vector_index(self, context: Context) -> dict:
            input_data = context.workflow_input()["request"]
            parsed_data = (
                IngestionServiceAdapter.parse_delete_vector_index_input(
                    input_data
                )
            )

            await self.ingestion_service.providers.database.delete_index(
                **parsed_data
            )

            return {"status": "Vector index deleted successfully."}

    @orchestration_provider.workflow(
        name="update-document-metadata",
        timeout="30m",
    )
    class HatchetUpdateDocumentMetadataWorkflow:
        def __init__(self, ingestion_service: IngestionService):
            self.ingestion_service = ingestion_service

        @orchestration_provider.step(timeout="30m")
        async def update_document_metadata(self, context: Context) -> dict:
            try:
                input_data = context.workflow_input()["request"]
                parsed_data = IngestionServiceAdapter.parse_update_document_metadata_input(
                    input_data
                )

                document_id = UUID(parsed_data["document_id"])
                metadata = parsed_data["metadata"]
                user = parsed_data["user"]

                await self.ingestion_service.update_document_metadata(
                    document_id=document_id,
                    metadata=metadata,
                    user=user,
                )

                return {
                    "message": "Document metadata update completed successfully.",
                    "document_id": str(document_id),
                    "task_id": context.workflow_run_id(),
                }

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error during document metadata update: {str(e)}",
                )

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            # Handle failure case if necessary
            pass

    # Add this to the workflows dictionary in hatchet_ingestion_factory
    ingest_files_workflow = HatchetIngestFilesWorkflow(service)
    update_files_workflow = HatchetUpdateFilesWorkflow(service)
    ingest_chunks_workflow = HatchetIngestChunksWorkflow(service)
    update_chunks_workflow = HatchetUpdateChunkWorkflow(service)
    update_document_metadata_workflow = HatchetUpdateDocumentMetadataWorkflow(
        service
    )
    create_vector_index_workflow = HatchetCreateVectorIndexWorkflow(service)
    delete_vector_index_workflow = HatchetDeleteVectorIndexWorkflow(service)

    return {
        "ingest_files": ingest_files_workflow,
        "update_files": update_files_workflow,
        "ingest_chunks": ingest_chunks_workflow,
        "update_chunk": update_chunks_workflow,
        "update_document_metadata": update_document_metadata_workflow,
        "create_vector_index": create_vector_index_workflow,
        "delete_vector_index": delete_vector_index_workflow,
    }
