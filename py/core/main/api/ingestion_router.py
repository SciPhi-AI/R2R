import base64
import logging
from io import BytesIO
from pathlib import Path as pathlib_Path
from typing import Optional, Union
from uuid import UUID

import yaml
from fastapi import Body, Depends, File, Form, Path, Query, UploadFile
from pydantic import Json

from core.base import R2RException, RawChunk, Workflow, generate_document_id
from core.base.abstractions import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)
from core.base.api.models import (
    WrappedCreateVectorIndexResponse,
    WrappedDeleteVectorIndexResponse,
    WrappedIngestionResponse,
    WrappedListVectorIndicesResponse,
    WrappedMetadataUpdateResponse,
    WrappedUpdateResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from ...base.logger.base import RunType
from ..services.ingestion_service import IngestionService
from .base_router import BaseRouter

logger = logging.getLogger()


class IngestionRouter(BaseRouter):
    def __init__(
        self,
        service: IngestionService,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.INGESTION,
    ):
        super().__init__(service, orchestration_provider, run_type)
        self.service: IngestionService = service

    def _register_workflows(self):
        self.orchestration_provider.register_workflows(
            Workflow.INGESTION,
            self.service,
            {
                "ingest-files": (
                    "Ingest files task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Ingestion task completed successfully."
                ),
                "ingest-chunks": (
                    "Ingest chunks task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Ingestion task completed successfully."
                ),
                "update-files": (
                    "Update file task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Update task queued successfully."
                ),
                "update-chunk": (
                    "Update chunk task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Chunk update completed successfully."
                ),
                "update-document-metadata": (
                    "Update document metadata task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Document metadata update completed successfully."
                ),
                "create-vector-index": (
                    "Vector index creation task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Vector index creation task completed successfully."
                ),
                "delete-vector-index": (
                    "Vector index deletion task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Vector index deletion task completed successfully."
                ),
                "select-vector-index": (
                    "Vector index selection task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Vector index selection task completed successfully."
                ),
            },
        )

    def _load_openapi_extras(self):
        yaml_path = (
            pathlib_Path(__file__).parent
            / "data"
            / "ingestion_router_openapi.yml"
        )
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def _setup_routes(self):
        # Note, we use the following verbose input parameters because FastAPI struggles to handle `File` input and `Body` inputs
        # at the same time. Therefore, we must ues `Form` inputs for the metadata, document_ids
        ingest_files_extras = self.openapi_extras.get("ingest_files", {})
        ingest_files_descriptions = ingest_files_extras.get(
            "input_descriptions", {}
        )

        @self.router.post(
            "/ingest_files",
            openapi_extra=ingest_files_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def ingest_files_app(
            files: list[UploadFile] = File(
                ..., description=ingest_files_descriptions.get("files")
            ),
            document_ids: Optional[Json[list[UUID]]] = Form(
                None,
                description=ingest_files_descriptions.get("document_ids"),
            ),
            collection_ids: Optional[Json[list[list[UUID]]]] = Form(
                None,
                description="Optional collection IDs for the documents, if provided the document will be assigned to them at ingestion.",
            ),
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description=ingest_files_descriptions.get("ingestion_config"),
            ),
            run_with_orchestration: Optional[bool] = Form(
                True,
                description=ingest_files_descriptions.get(
                    "run_with_orchestration"
                ),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:  # type: ignore
            """
            Ingests files into R2R, resulting in stored `Document` objects. Each document has corresponding `Chunk` objects which are used in vector indexing and search.

            This endpoint supports multipart/form-data requests.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access.
            """
            # Check if the user is a superuser
            if not auth_user.is_superuser:
                for metadata in metadatas or []:
                    if "user_id" in metadata and (
                        not auth_user.is_superuser
                        and metadata["user_id"] != str(auth_user.id)
                    ):
                        raise R2RException(
                            status_code=403,
                            message="Non-superusers cannot set user_id in metadata.",
                        )
                    # If user is not a superuser, set user_id in metadata
                    metadata["user_id"] = str(auth_user.id)

            file_datas = await self._process_files(files)

            messages: list[dict[str, Union[str, None]]] = []
            for it, file_data in enumerate(file_datas):
                content_length = len(file_data["content"])
                file_content = BytesIO(base64.b64decode(file_data["content"]))

                file_data.pop("content", None)
                document_id = (
                    document_ids[it]
                    if document_ids
                    else generate_document_id(
                        file_data["filename"], auth_user.id
                    )
                )

                workflow_input = {
                    "file_data": file_data,
                    "document_id": str(document_id),
                    "metadata": metadatas[it] if metadatas else None,
                    "ingestion_config": ingestion_config,
                    "user": auth_user.model_dump_json(),
                    "size_in_bytes": content_length,
                    "collection_ids": (
                        collection_ids[it] if collection_ids else None
                    ),
                    "is_update": False,
                }

                file_name = file_data["filename"]
                await self.service.providers.database.store_file(
                    document_id,
                    file_name,
                    file_content,
                    file_data["content_type"],
                )
                if run_with_orchestration:
                    raw_message: dict[str, Union[str, None]] = await self.orchestration_provider.run_workflow(  # type: ignore
                        "ingest-files",
                        {"request": workflow_input},
                        options={
                            "additional_metadata": {
                                "document_id": str(document_id),
                            }
                        },
                    )
                    raw_message["document_id"] = str(document_id)
                    messages.append(raw_message)
                else:
                    logger.info(
                        f"Running ingestion without orchestration for file {file_name} and document_id {document_id}."
                    )
                    # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                    from core.main.orchestration import (
                        simple_ingestion_factory,
                    )

                    simple_ingestor = simple_ingestion_factory(self.service)
                    await simple_ingestor["ingest-files"](workflow_input)
                    messages.append(
                        {
                            "message": "Ingestion task completed successfully.",
                            "document_id": str(document_id),
                            "task_id": None,
                        }
                    )

            return messages  # type: ignore

        update_files_extras = self.openapi_extras.get("update_files", {})
        update_files_descriptions = update_files_extras.get(
            "input_descriptions", {}
        )

        @self.router.post(
            "/update_files",
            openapi_extra=update_files_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def update_files_app(
            files: list[UploadFile] = File(
                ..., description=update_files_descriptions.get("files")
            ),
            document_ids: Optional[Json[list[UUID]]] = Form(
                None, description=ingest_files_descriptions.get("document_ids")
            ),
            collection_ids: Optional[Json[list[list[UUID]]]] = Form(
                None,
                description="Optional collection IDs for the documents, if provided the document will be assigned to them at ingestion.",
            ),
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description=ingest_files_descriptions.get("ingestion_config"),
            ),
            run_with_orchestration: Optional[bool] = Form(
                True,
                description=ingest_files_descriptions.get(
                    "run_with_orchestration"
                ),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUpdateResponse:
            """
            Ingests updated files into R2R, updating the corresponding `Document` and `Chunk` objects from previous ingestion.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only update their own files.
            """
            if not auth_user.is_superuser:
                for metadata in metadatas or []:
                    if "user_id" in metadata and metadata["user_id"] != str(
                        auth_user.id
                    ):
                        raise R2RException(
                            status_code=403,
                            message="Non-superusers cannot set user_id in metadata.",
                        )
                    metadata["user_id"] = str(auth_user.id)

            file_datas = await self._process_files(files)

            processed_data = []
            for it, file_data in enumerate(file_datas):
                content = base64.b64decode(file_data.pop("content"))
                document_id = (
                    document_ids[it]
                    if document_ids
                    else generate_document_id(
                        file_data["filename"], auth_user.id
                    )
                )

                await self.service.providers.database.store_file(
                    document_id,
                    file_data["filename"],
                    BytesIO(content),
                    file_data["content_type"],
                )

                processed_data.append(
                    {
                        "file_data": file_data,
                        "file_length": len(content),
                        "document_id": str(document_id),
                    }
                )

            workflow_input = {
                "file_datas": [item["file_data"] for item in processed_data],
                "file_sizes_in_bytes": [
                    item["file_length"] for item in processed_data
                ],
                "document_ids": [
                    item["document_id"] for item in processed_data
                ],
                "metadatas": metadatas,
                "ingestion_config": ingestion_config,
                "user": auth_user.model_dump_json(),
                "is_update": True,
                "collection_ids": collection_ids,
            }

            if run_with_orchestration:
                raw_message: dict[str, Union[str, None]] = await self.orchestration_provider.run_workflow(  # type: ignore
                    "update-files", {"request": workflow_input}, {}
                )
                raw_message["message"] = "Update task queued successfully."
                raw_message["document_ids"] = workflow_input["document_ids"]

                return raw_message  # type: ignore
            else:
                logger.info("Running update without orchestration.")
                # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(self.service)
                await simple_ingestor["update-files"](workflow_input)
                return {  # type: ignore
                    "message": "Update task completed successfully.",
                    "document_ids": workflow_input["document_ids"],
                    "task_id": None,
                }

        ingest_chunks_extras = self.openapi_extras.get("ingest_chunks", {})
        ingest_chunks_descriptions = ingest_chunks_extras.get(
            "input_descriptions", {}
        )

        @self.router.post(
            "/ingest_chunks",
            openapi_extra=ingest_chunks_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def ingest_chunks_app(
            chunks: list[RawChunk] = Body(
                {}, description=ingest_chunks_descriptions.get("chunks")
            ),
            document_id: Optional[str] = Body(
                None, description=ingest_chunks_descriptions.get("document_id")
            ),
            metadata: Optional[dict] = Body(
                None, description=ingest_files_descriptions.get("metadata")
            ),
            collection_ids: Optional[Json[list[list[UUID]]]] = Body(
                None,
                description="Optional collection IDs for the documents, if provided the document will be assigned to them at ingestion.",
            ),
            run_with_orchestration: Optional[bool] = Body(
                True,
                description=ingest_files_descriptions.get(
                    "run_with_orchestration"
                ),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Ingests `Chunk` objects into the system as raw text and associated metadata.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest chunks for their own access.
            """
            if document_id:
                try:
                    document_uuid = UUID(document_id)
                except ValueError:
                    raise R2RException(
                        status_code=422, message="Invalid document ID format."
                    )

            if not document_id:
                document_uuid = generate_document_id(
                    chunks[0].text[:20], auth_user.id
                )

            workflow_input = {
                "document_id": str(document_uuid),
                "chunks": [chunk.model_dump() for chunk in chunks],
                "metadata": metadata or {},
                "user": auth_user.model_dump_json(),
                "collection_ids": collection_ids,
            }
            if run_with_orchestration:
                raw_message = await self.orchestration_provider.run_workflow(
                    "ingest-chunks",
                    {"request": workflow_input},
                    options={
                        "additional_metadata": {
                            "document_id": str(document_uuid),
                        }
                    },
                )
                raw_message["document_id"] = str(document_uuid)

                return [raw_message]  # type: ignore
            else:
                logger.info("Running ingest chunks without orchestration.")
                # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(self.service)
                await simple_ingestor["ingest-chunks"](workflow_input)
                return [
                    {  # type: ignore
                        "message": "Ingestion task completed successfully.",
                        "document_id": str(document_uuid),
                        "task_id": None,
                    }
                ]

        @self.router.post(
            "/update_document_metadata/{document_id}",
        )
        @self.base_endpoint
        async def update_document_metadata_app(
            document_id: UUID = Path(
                ..., description="The document ID of the document to update"
            ),
            metadata: dict = Body(
                ...,
                description="The new metadata to merge with existing metadata",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedMetadataUpdateResponse:
            """
            Updates the metadata of a previously ingested document and its associated chunks.

            A valid user authentication token is required to access this endpoint, as regular users can only update their own documents.
            """

            try:
                workflow_input = {
                    "document_id": str(document_id),
                    "metadata": metadata,
                    "user": auth_user.model_dump_json(),
                }

                logger.info(
                    "Running document metadata update without orchestration."
                )
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(self.service)
                await simple_ingestor["update-document-metadata"](
                    workflow_input
                )

                return {  # type: ignore
                    "message": "Update metadata task completed successfully.",
                    "document_id": str(document_id),
                    "task_id": None,
                }

            except Exception as e:
                raise R2RException(
                    status_code=500,
                    message=f"Error updating document metadata: {str(e)}",
                )

        @self.router.put(
            "/update_chunk/{document_id}/{extraction_id}",
        )
        @self.base_endpoint
        async def update_chunk_app(
            document_id: UUID = Path(
                ..., description="The document ID of the chunk to update"
            ),
            extraction_id: UUID = Path(
                ..., description="The extraction ID of the chunk to update"
            ),
            text: str = Body(
                ..., description="The new text content for the chunk"
            ),
            metadata: Optional[dict] = Body(
                None, description="Optional updated metadata"
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUpdateResponse:
            """
            Updates a previously ingested `Chunk` object into the system as raw text and associated metadata.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest chunks for their own access.
            """

            try:
                workflow_input = {
                    "document_id": str(document_id),
                    "extraction_id": str(extraction_id),
                    "text": text,
                    "metadata": metadata,
                    "user": auth_user.model_dump_json(),
                }

                if run_with_orchestration:
                    raw_message: dict[str, Union[str, None]] = await self.orchestration_provider.run_workflow(  # type: ignore
                        "update-chunk", {"request": workflow_input}, {}
                    )
                    raw_message["message"] = "Update task queued successfully."
                    raw_message["document_ids"] = [document_id]  # type: ignore

                    return raw_message  # type: ignore
                else:
                    logger.info("Running chunk update without orchestration.")
                    from core.main.orchestration import (
                        simple_ingestion_factory,
                    )

                    simple_ingestor = simple_ingestion_factory(self.service)
                    await simple_ingestor["update-chunk"](workflow_input)

                    return {  # type: ignore
                        "message": "Update task completed successfully.",
                        "document_ids": workflow_input["document_ids"],
                        "task_id": None,
                    }

            except Exception as e:
                raise R2RException(
                    status_code=500, message=f"Error updating chunk: {str(e)}"
                )

        create_vector_index_extras = self.openapi_extras.get(
            "create_vector_index", {}
        )
        create_vector_descriptions = create_vector_index_extras.get(
            "input_descriptions", {}
        )

        @self.router.post(
            "/create_vector_index",
            openapi_extra=create_vector_index_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def create_vector_index_app(
            table_name: Optional[VectorTableName] = Body(
                default=VectorTableName.VECTORS,
                description=create_vector_descriptions.get("table_name"),
            ),
            index_method: IndexMethod = Body(
                default=IndexMethod.hnsw,
                description=create_vector_descriptions.get("index_method"),
            ),
            index_measure: IndexMeasure = Body(
                default=IndexMeasure.cosine_distance,
                description=create_vector_descriptions.get("index_measure"),
            ),
            index_arguments: Optional[
                Union[IndexArgsIVFFlat, IndexArgsHNSW]
            ] = Body(
                None,
                description=create_vector_descriptions.get("index_arguments"),
            ),
            index_name: Optional[str] = Body(
                None,
                description=create_vector_descriptions.get("index_name"),
            ),
            index_column: Optional[str] = Body(
                None,
                description=create_vector_descriptions.get("index_column"),
            ),
            concurrently: bool = Body(
                default=True,
                description=create_vector_descriptions.get("concurrently"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCreateVectorIndexResponse:
            """
            Create a vector index for a given table.

            """

            logger.info(
                f"Creating vector index for {table_name} with method {index_method}, measure {index_measure}, concurrently {concurrently}"
            )

            raw_message = await self.orchestration_provider.run_workflow(
                "create-vector-index",
                {
                    "request": {
                        "table_name": table_name,
                        "index_method": index_method,
                        "index_measure": index_measure,
                        "index_name": index_name,
                        "index_column": index_column,
                        "index_arguments": index_arguments,
                        "concurrently": concurrently,
                    },
                },
                options={
                    "additional_metadata": {},
                },
            )

            return raw_message  # type: ignore

        list_vector_indices_extras = self.openapi_extras.get(
            "create_vector_index", {}
        )
        list_vector_indices_descriptions = list_vector_indices_extras.get(
            "input_descriptions", {}
        )

        @self.router.get(
            "/list_vector_indices",
            openapi_extra=list_vector_indices_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def list_vector_indices_app(
            table_name: Optional[VectorTableName] = Query(
                default=VectorTableName.VECTORS,
                description=list_vector_indices_descriptions.get("table_name"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedListVectorIndicesResponse:
            indices = await self.service.providers.database.list_indices(
                table_name=table_name
            )
            return {"indices": indices}  # type: ignore

        delete_vector_index_extras = self.openapi_extras.get(
            "delete_vector_index", {}
        )
        delete_vector_index_descriptions = delete_vector_index_extras.get(
            "input_descriptions", {}
        )

        @self.router.delete(
            "/delete_vector_index",
            openapi_extra=delete_vector_index_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def delete_vector_index_app(
            index_name: str = Body(
                ...,
                description=delete_vector_index_descriptions.get("index_name"),
            ),
            table_name: Optional[VectorTableName] = Body(
                default=VectorTableName.VECTORS,
                description=delete_vector_index_descriptions.get("table_name"),
            ),
            concurrently: bool = Body(
                default=True,
                description=delete_vector_index_descriptions.get(
                    "concurrently"
                ),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDeleteVectorIndexResponse:
            logger.info(
                f"Deleting vector index {index_name} from table {table_name}"
            )

            raw_message = await self.orchestration_provider.run_workflow(
                "delete-vector-index",
                {
                    "request": {
                        "index_name": index_name,
                        "table_name": table_name,
                        "concurrently": concurrently,
                    },
                },
                options={
                    "additional_metadata": {},
                },
            )

            return raw_message  # type: ignore

    @staticmethod
    async def _process_files(files):
        import base64

        file_datas = []
        for file in files:
            content = await file.read()
            file_datas.append(
                {
                    "filename": file.filename,
                    "content": base64.b64encode(content).decode("utf-8"),
                    "content_type": file.content_type,
                }
            )
        return file_datas
