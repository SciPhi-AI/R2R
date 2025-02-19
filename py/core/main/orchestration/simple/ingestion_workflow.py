import asyncio
import logging
from uuid import UUID

import tiktoken
from fastapi import HTTPException
from litellm import AuthenticationError

from core.base import (
    DocumentChunk,
    GraphConstructionStatus,
    R2RException,
    increment_version,
)
from core.utils import (
    generate_default_user_collection_id,
    generate_extraction_id,
    update_settings_from_dict,
)

from ...services import IngestionService

logger = logging.getLogger()


def count_tokens_for_text(text: str, model: str = "gpt-4o") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to a known encoding if model not recognized
        encoding = tiktoken.get_encoding("cl100k_base")

    return len(encoding.encode(text, disallowed_special=()))


def simple_ingestion_factory(service: IngestionService):
    async def ingest_files(input_data):
        document_info = None
        try:
            from core.base import IngestionStatus
            from core.main import IngestionServiceAdapter

            parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
                input_data
            )
            # ingestion_result = await service.ingest_file_ingress(**parsed_data)
            # document_info = ingestion_result["info"]

            document_info = service.create_document_info_from_file(
                parsed_data["document_id"],
                parsed_data["user"],
                parsed_data["file_data"]["filename"],
                parsed_data["metadata"],
                parsed_data["version"],
                parsed_data["size_in_bytes"],
            )

            await service.update_document_status(
                document_info, status=IngestionStatus.PARSING
            )

            ingestion_config = parsed_data["ingestion_config"]
            extractions_generator = service.parse_file(
                document_info, ingestion_config
            )
            extractions = [
                extraction.model_dump()
                async for extraction in extractions_generator
            ]

            # 2) Sum tokens
            total_tokens = 0
            for chunk_dict in extractions:
                text_data = chunk_dict["data"]
                if not isinstance(text_data, str):
                    text_data = text_data.decode("utf-8", errors="ignore")
                total_tokens += count_tokens_for_text(text_data)
            document_info.total_tokens = total_tokens

            if not ingestion_config.get("skip_document_summary", False):
                await service.update_document_status(
                    document_info, status=IngestionStatus.AUGMENTING
                )
                await service.augment_document_info(document_info, extractions)

            await service.update_document_status(
                document_info, status=IngestionStatus.EMBEDDING
            )
            embedding_generator = service.embed_document(extractions)
            embeddings = [
                embedding.model_dump()
                async for embedding in embedding_generator
            ]

            await service.update_document_status(
                document_info, status=IngestionStatus.STORING
            )
            storage_generator = service.store_embeddings(embeddings)
            async for _ in storage_generator:
                pass

            await service.finalize_ingestion(document_info)

            await service.update_document_status(
                document_info, status=IngestionStatus.SUCCESS
            )

            collection_ids = parsed_data.get("collection_ids")

            try:
                if not collection_ids:
                    # TODO: Move logic onto the `management service`
                    collection_id = generate_default_user_collection_id(
                        document_info.owner_id
                    )
                    await service.providers.database.collections_handler.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.chunks_handler.assign_document_chunks_to_collection(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.documents_handler.set_workflow_status(
                        id=collection_id,
                        status_type="graph_sync_status",
                        status=GraphConstructionStatus.OUTDATED,
                    )
                    await service.providers.database.documents_handler.set_workflow_status(
                        id=collection_id,
                        status_type="graph_cluster_status",
                        status=GraphConstructionStatus.OUTDATED,  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                    )
                else:
                    for collection_id in collection_ids:
                        try:
                            # FIXME: Right now we just throw a warning if the collection already exists, but we should probably handle this more gracefully
                            name = "My Collection"
                            description = f"A collection started during {document_info.title} ingestion"

                            await service.providers.database.collections_handler.create_collection(
                                owner_id=document_info.owner_id,
                                name=name,
                                description=description,
                                collection_id=collection_id,
                            )
                            await service.providers.database.graphs_handler.create(
                                collection_id=collection_id,
                                name=name,
                                description=description,
                                graph_id=collection_id,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Warning, could not create collection with error: {str(e)}"
                            )

                        await service.providers.database.collections_handler.assign_document_to_collection_relational(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )

                        await service.providers.database.chunks_handler.assign_document_chunks_to_collection(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.documents_handler.set_workflow_status(
                            id=collection_id,
                            status_type="graph_sync_status",
                            status=GraphConstructionStatus.OUTDATED,
                        )
                        await service.providers.database.documents_handler.set_workflow_status(
                            id=collection_id,
                            status_type="graph_cluster_status",
                            status=GraphConstructionStatus.OUTDATED,  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                        )
            except Exception as e:
                logger.error(
                    f"Error during assigning document to collection: {str(e)}"
                )

            # Chunk enrichment
            if server_chunk_enrichment_settings := getattr(
                service.providers.ingestion.config,
                "chunk_enrichment_settings",
                None,
            ):
                chunk_enrichment_settings = update_settings_from_dict(
                    server_chunk_enrichment_settings,
                    ingestion_config.get("chunk_enrichment_settings", {})
                    or {},
                )

                if chunk_enrichment_settings.enable_chunk_enrichment:
                    logger.info("Enriching document with contextual chunks")

                    # Get updated document info with collection IDs
                    document_info = (
                        await service.providers.database.documents_handler.get_documents_overview(
                            offset=0,
                            limit=100,
                            filter_user_ids=[document_info.owner_id],
                            filter_document_ids=[document_info.id],
                        )
                    )["results"][0]

                    await service.update_document_status(
                        document_info,
                        status=IngestionStatus.ENRICHING,
                    )

                    await service.chunk_enrichment(
                        document_id=document_info.id,
                        document_summary=document_info.summary,
                        chunk_enrichment_settings=chunk_enrichment_settings,
                    )

                    await service.update_document_status(
                        document_info,
                        status=IngestionStatus.SUCCESS,
                    )

            # Automatic extraction
            if service.providers.ingestion.config.automatic_extraction:
                logger.warning(
                    "Automatic extraction not yet implemented for `simple` ingestion workflows."
                )

        except AuthenticationError as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info,
                    status=IngestionStatus.FAILED,
                    metadata={"failure": f"{str(e)}"},
                )
            raise R2RException(
                status_code=401,
                message="Authentication error: Invalid API key or credentials.",
            ) from e
        except Exception as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info,
                    status=IngestionStatus.FAILED,
                    metadata={"failure": f"{str(e)}"},
                )
            if isinstance(e, R2RException):
                raise
            raise HTTPException(
                status_code=500, detail=f"Error during ingestion: {str(e)}"
            ) from e

    async def update_files(input_data):
        from core.main import IngestionServiceAdapter

        parsed_data = IngestionServiceAdapter.parse_update_files_input(
            input_data
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
            ) from None
        if len(document_ids) != len(file_datas):
            raise R2RException(
                status_code=400,
                message="Number of ids does not match number of files.",
            ) from None

        documents_overview = (
            await service.providers.database.documents_handler.get_documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                offset=0,
                limit=100,
                filter_user_ids=None if user.is_superuser else [user.id],
                filter_document_ids=document_ids,
            )
        )["results"]

        if len(documents_overview) != len(document_ids):
            raise R2RException(
                status_code=404,
                message="One or more documents not found.",
            ) from None

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
                strict=False,
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

            ingest_input = {
                "file_data": file_data,
                "user": user.model_dump(),
                "metadata": updated_metadata,
                "document_id": str(doc_id),
                "version": new_version,
                "ingestion_config": ingestion_config,
                "size_in_bytes": file_size_in_bytes,
            }

            result = ingest_files(ingest_input)
            results.append(result)

        await asyncio.gather(*results)
        if service.providers.ingestion.config.automatic_extraction:
            raise R2RException(
                status_code=501,
                message="Automatic extraction not yet implemented for `simple` ingestion workflows.",
            ) from None

    async def ingest_chunks(input_data):
        document_info = None
        try:
            from core.base import IngestionStatus
            from core.main import IngestionServiceAdapter

            parsed_data = IngestionServiceAdapter.parse_ingest_chunks_input(
                input_data
            )

            document_info = await service.ingest_chunks_ingress(**parsed_data)

            await service.update_document_status(
                document_info, status=IngestionStatus.EMBEDDING
            )
            document_id = document_info.id

            extractions = [
                DocumentChunk(
                    id=(
                        generate_extraction_id(document_id, i)
                        if chunk.id is None
                        else chunk.id
                    ),
                    document_id=document_id,
                    collection_ids=[],
                    owner_id=document_info.owner_id,
                    data=chunk.text,
                    metadata=parsed_data["metadata"],
                ).model_dump()
                for i, chunk in enumerate(parsed_data["chunks"])
            ]

            embedding_generator = service.embed_document(extractions)
            embeddings = [
                embedding.model_dump()
                async for embedding in embedding_generator
            ]

            await service.update_document_status(
                document_info, status=IngestionStatus.STORING
            )
            storage_generator = service.store_embeddings(embeddings)
            async for _ in storage_generator:
                pass

            await service.finalize_ingestion(document_info)

            await service.update_document_status(
                document_info, status=IngestionStatus.SUCCESS
            )

            collection_ids = parsed_data.get("collection_ids")

            try:
                # TODO - Move logic onto management service
                if not collection_ids:
                    collection_id = generate_default_user_collection_id(
                        document_info.owner_id
                    )

                    await service.providers.database.collections_handler.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )

                    await service.providers.database.chunks_handler.assign_document_chunks_to_collection(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )

                    await service.providers.database.documents_handler.set_workflow_status(
                        id=collection_id,
                        status_type="graph_sync_status",
                        status=GraphConstructionStatus.OUTDATED,
                    )
                    await service.providers.database.documents_handler.set_workflow_status(
                        id=collection_id,
                        status_type="graph_cluster_status",
                        status=GraphConstructionStatus.OUTDATED,  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                    )

                else:
                    for collection_id in collection_ids:
                        try:
                            name = document_info.title or "N/A"
                            description = ""
                            result = await service.providers.database.collections_handler.create_collection(
                                owner_id=document_info.owner_id,
                                name=name,
                                description=description,
                                collection_id=collection_id,
                            )
                            await service.providers.database.graphs_handler.create(
                                collection_id=collection_id,
                                name=name,
                                description=description,
                                graph_id=collection_id,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Warning, could not create collection with error: {str(e)}"
                            )
                        await service.providers.database.collections_handler.assign_document_to_collection_relational(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.chunks_handler.assign_document_chunks_to_collection(
                            document_id=document_info.id,
                            collection_id=collection_id,
                        )
                        await service.providers.database.documents_handler.set_workflow_status(
                            id=collection_id,
                            status_type="graph_sync_status",
                            status=GraphConstructionStatus.OUTDATED,
                        )
                        await service.providers.database.documents_handler.set_workflow_status(
                            id=collection_id,
                            status_type="graph_cluster_status",
                            status=GraphConstructionStatus.OUTDATED,  # NOTE - we should actually check that cluster has been made first, if not it should be PENDING still
                        )

                    if service.providers.ingestion.config.automatic_extraction:
                        raise R2RException(
                            status_code=501,
                            message="Automatic extraction not yet implemented for `simple` ingestion workflows.",
                        ) from None

            except Exception as e:
                logger.error(
                    f"Error during assigning document to collection: {str(e)}"
                )

        except Exception as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info,
                    status=IngestionStatus.FAILED,
                    metadata={"failure": f"{str(e)}"},
                )
            raise HTTPException(
                status_code=500,
                detail=f"Error during chunk ingestion: {str(e)}",
            ) from e

    async def update_chunk(input_data):
        from core.main import IngestionServiceAdapter

        try:
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

            await service.update_chunk_ingress(
                document_id=document_uuid,
                chunk_id=extraction_uuid,
                text=parsed_data.get("text"),
                user=parsed_data["user"],
                metadata=parsed_data.get("metadata"),
                collection_ids=parsed_data.get("collection_ids"),
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during chunk update: {str(e)}",
            ) from e

    async def create_vector_index(input_data):
        try:
            from core.main import IngestionServiceAdapter

            parsed_data = (
                IngestionServiceAdapter.parse_create_vector_index_input(
                    input_data
                )
            )

            await service.providers.database.chunks_handler.create_index(
                **parsed_data
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during vector index creation: {str(e)}",
            ) from e

    async def delete_vector_index(input_data):
        try:
            from core.main import IngestionServiceAdapter

            parsed_data = (
                IngestionServiceAdapter.parse_delete_vector_index_input(
                    input_data
                )
            )

            await service.providers.database.chunks_handler.delete_index(
                **parsed_data
            )

            return {"status": "Vector index deleted successfully."}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during vector index deletion: {str(e)}",
            ) from e

    async def update_document_metadata(input_data):
        try:
            from core.main import IngestionServiceAdapter

            parsed_data = (
                IngestionServiceAdapter.parse_update_document_metadata_input(
                    input_data
                )
            )

            document_id = parsed_data["document_id"]
            metadata = parsed_data["metadata"]
            user = parsed_data["user"]

            await service.update_document_metadata(
                document_id=document_id,
                metadata=metadata,
                user=user,
            )

            return {
                "message": "Document metadata update completed successfully.",
                "document_id": str(document_id),
                "task_id": None,
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during document metadata update: {str(e)}",
            ) from e

    return {
        "ingest-files": ingest_files,
        "ingest-chunks": ingest_chunks,
        "update-chunk": update_chunk,
        "update-document-metadata": update_document_metadata,
        "create-vector-index": create_vector_index,
        "delete-vector-index": delete_vector_index,
    }
