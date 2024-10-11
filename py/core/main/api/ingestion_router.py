import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import yaml
from fastapi import Body, Depends, File, Form, UploadFile
from pydantic import Json

from core.base import R2RException, RawChunk, generate_document_id

from core.base.api.models import (
    WrappedIngestionResponse,
    WrappedUpdateResponse,
    WrappedCreateVectorIndexResponse,
)
from core.base.providers import OrchestrationProvider, Workflow

from ..services.ingestion_service import IngestionService
from .base_router import BaseRouter, RunType

from shared.abstractions.vector import (
    IndexMethod,
    IndexArgsIVFFlat,
    IndexArgsHNSW,
    VectorTableName,
    IndexMeasure,
)

logger = logging.getLogger(__name__)


class IngestionRouter(BaseRouter):
    def __init__(
        self,
        service: IngestionService,
        orchestration_provider: OrchestrationProvider,
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
                "create-vector-index": (
                    "Vector index creation task queued successfully."
                    if self.orchestration_provider.config.provider != "simple"
                    else "Vector index creation task completed successfully."
                ),
            },
        )

    def _load_openapi_extras(self):
        yaml_path = (
            Path(__file__).parent / "data" / "ingestion_router_openapi.yml"
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
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description=ingest_files_descriptions.get("ingestion_config"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:  # type: ignore
            """
            Ingest files into the system.

            This endpoint supports multipart/form-data requests, enabling you to ingest files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access. More expansive collection permissioning is under development.
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
                    "is_update": False,
                }

                file_name = file_data["filename"]
                await self.service.providers.file.store_file(
                    document_id,
                    file_name,
                    file_content,
                    file_data["content_type"],
                )
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
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description=ingest_files_descriptions.get("ingestion_config"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUpdateResponse:
            """
            Update existing files in the system.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only update their own files. More expansive collection permissioning is under development.
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

                await self.service.providers.file.store_file(
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
            }

            raw_message: dict[str, Union[str, None]] = await self.orchestration_provider.run_workflow(  # type: ignore
                "update-files", {"request": workflow_input}, {}
            )
            raw_message["message"] = "Update task queued successfully."
            raw_message["document_ids"] = workflow_input["document_ids"]

            return raw_message  # type: ignore

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
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Ingest text chunks into the system.

            This endpoint supports multipart/form-data requests, enabling you to ingest pre-parsed text chunks into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest chunks for their own access. More expansive collection permissioning is under development.
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
            }

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

        @self.router.post("/create_vector_index")
        @self.base_endpoint
        async def create_vector_index_app(
            table_name: Optional[VectorTableName] = Body(
                default=VectorTableName.CHUNKS,
                description="The name of the vector table to create.",
            ),
            index_method: IndexMethod = Body(
                default=IndexMethod.hnsw,
                description="The type of vector index to create.",
            ),
            measure: IndexMeasure = Body(
                default=IndexMeasure.cosine_distance,
                description="The measure for the index.",
            ),
            index_arguments: Optional[
                Union[IndexArgsIVFFlat, IndexArgsHNSW]
            ] = Body(
                None,
                description="The arguments for the index method.",
            ),
            replace: bool = Body(
                default=True,
                description="Whether to replace an existing index.",
            ),
            concurrently: bool = Body(
                default=True,
                description="Whether to create the index concurrently.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCreateVectorIndexResponse:

            logger.info(
                f"Creating vector index for {table_name} with method {index_method}, measure {measure}, replace {replace}, concurrently {concurrently}"
            )

            raw_message = await self.orchestration_provider.run_workflow(
                "create-vector-index",
                {
                    "request": {
                        "table_name": table_name,
                        "index_method": index_method,
                        "measure": measure,
                        "index_arguments": index_arguments,
                        "replace": replace,
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
