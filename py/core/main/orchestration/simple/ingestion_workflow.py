import asyncio
import logging
from uuid import UUID

from litellm import AuthenticationError

from fastapi import HTTPException
from core.base import DocumentExtraction, R2RException, increment_version
from core.utils import (
    generate_default_user_collection_id,
    generate_extraction_id,
)

from ...services import IngestionService

logger = logging.getLogger()


def simple_ingestion_factory(service: IngestionService):
    async def ingest_files(input_data):
        document_info = None
        try:
            from core.base import IngestionStatus
            from core.main import IngestionServiceAdapter

            parsed_data = IngestionServiceAdapter.parse_ingest_file_input(
                input_data
            )
            is_update = parsed_data["is_update"]

            ingestion_result = await service.ingest_file_ingress(**parsed_data)
            document_info = ingestion_result["info"]

            await service.update_document_status(
                document_info, status=IngestionStatus.PARSING
            )

            ingestion_config = parsed_data["ingestion_config"]
            extractions_generator = await service.parse_file(
                document_info, ingestion_config
            )
            extractions = [
                extraction.model_dump()
                async for extraction in extractions_generator
            ]

            await service.update_document_status(
                document_info, status=IngestionStatus.EMBEDDING
            )
            embedding_generator = await service.embed_document(extractions)
            embeddings = [
                embedding.model_dump()
                async for embedding in embedding_generator
            ]

            await service.update_document_status(
                document_info, status=IngestionStatus.STORING
            )
            storage_generator = await service.store_embeddings(embeddings)
            async for _ in storage_generator:
                pass

            await service.finalize_ingestion(
                document_info, is_update=is_update
            )

            await service.update_document_status(
                document_info, status=IngestionStatus.SUCCESS
            )

            collection_ids = parsed_data.get("collection_ids")

            try:
                if not collection_ids:
                    # TODO: Move logic onto the `management service`
                    collection_id = generate_default_user_collection_id(
                        document_info.user_id
                    )
                    await service.providers.database.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.assign_document_to_collection_vector(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                else:
                    for collection_id in collection_ids:
                        try:
                            await service.providers.database.create_collection(
                                name=document_info.title,
                                collection_id=collection_id,
                                description="",
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
            except Exception as e:
                logger.error(
                    f"Error during assigning document to collection: {str(e)}"
                )

        except AuthenticationError as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info, status=IngestionStatus.FAILED
                )
            raise R2RException(
                status_code=401,
                message="Authentication error: Invalid API key or credentials.",
            )
        except Exception as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info, status=IngestionStatus.FAILED
                )
            raise HTTPException(
                status_code=500, detail=f"Error during ingestion: {str(e)}"
            )

    async def update_files(input_data):
        from core.base import IngestionStatus
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
            )
        if len(document_ids) != len(file_datas):
            raise R2RException(
                status_code=400,
                message="Number of ids does not match number of files.",
            )

        documents_overview = (
            await service.providers.database.get_documents_overview(
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

            ingest_input = {
                "file_data": file_data,
                "user": user.model_dump(),
                "metadata": updated_metadata,
                "document_id": str(doc_id),
                "version": new_version,
                "ingestion_config": ingestion_config,
                "size_in_bytes": file_size_in_bytes,
                "is_update": True,
            }

            result = ingest_files(ingest_input)
            results.append(result)

        await asyncio.gather(*results)

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
                DocumentExtraction(
                    id=generate_extraction_id(document_id, i),
                    document_id=document_id,
                    collection_ids=[],
                    user_id=document_info.user_id,
                    data=chunk.text,
                    metadata=parsed_data["metadata"],
                ).model_dump()
                for i, chunk in enumerate(parsed_data["chunks"])
            ]

            embedding_generator = await service.embed_document(extractions)
            embeddings = [
                embedding.model_dump()
                async for embedding in embedding_generator
            ]

            await service.update_document_status(
                document_info, status=IngestionStatus.STORING
            )
            storage_generator = await service.store_embeddings(embeddings)
            async for _ in storage_generator:
                pass

            await service.finalize_ingestion(document_info, is_update=False)

            await service.update_document_status(
                document_info, status=IngestionStatus.SUCCESS
            )

            collection_ids = parsed_data.get("collection_ids")

            try:
                # TODO - Move logic onto management service
                if not collection_ids:
                    # TODO: Move logic onto the `management service`
                    collection_id = generate_default_user_collection_id(
                        document_info.user_id
                    )
                    await service.providers.database.assign_document_to_collection_relational(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                    await service.providers.database.assign_document_to_collection_vector(
                        document_id=document_info.id,
                        collection_id=collection_id,
                    )
                else:
                    for collection_id in collection_ids:
                        try:
                            await service.providers.database.create_collection(
                                name=document_info.title,
                                collection_id=collection_id,
                                description="",
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
            except Exception as e:
                logger.error(
                    f"Error during assigning document to collection: {str(e)}"
                )

        except Exception as e:
            if document_info is not None:
                await service.update_document_status(
                    document_info, status=IngestionStatus.FAILED
                )
            raise HTTPException(
                status_code=500,
                detail=f"Error during chunk ingestion: {str(e)}",
            )

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
                UUID(parsed_data["extraction_id"])
                if isinstance(parsed_data["extraction_id"], str)
                else parsed_data["extraction_id"]
            )

            await service.update_chunk_ingress(
                document_id=document_uuid,
                extraction_id=extraction_uuid,
                text=parsed_data.get("text"),
                user=parsed_data["user"],
                metadata=parsed_data.get("metadata"),
                collection_ids=parsed_data.get("collection_ids"),
            )

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during chunk update: {str(e)}",
            )

    async def create_vector_index(input_data):

        try:
            from core.main import IngestionServiceAdapter

            parsed_data = (
                IngestionServiceAdapter.parse_create_vector_index_input(
                    input_data
                )
            )

            await service.providers.database.create_index(**parsed_data)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during vector index creation: {str(e)}",
            )

    async def delete_vector_index(input_data):
        try:
            from core.main import IngestionServiceAdapter

            parsed_data = (
                IngestionServiceAdapter.parse_delete_vector_index_input(
                    input_data
                )
            )

            await service.providers.database.delete_index(**parsed_data)

            return {"status": "Vector index deleted successfully."}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error during vector index deletion: {str(e)}",
            )

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
            )

    return {
        "ingest-files": ingest_files,
        "update-files": update_files,
        "ingest-chunks": ingest_chunks,
        "update-chunk": update_chunk,
        "update-document-metadata": update_document_metadata,
        "create-vector-index": create_vector_index,
        "delete-vector-index": delete_vector_index,
    }
