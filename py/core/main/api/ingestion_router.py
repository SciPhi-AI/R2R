import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import UUID

import yaml
from fastapi import Depends, File, Form, UploadFile
from pydantic import Json

from core.base import ChunkingConfig, R2RException, generate_user_document_id
from core.base.api.models.ingestion.responses import (
    WrappedIngestionResponse,
    WrappedUpdateResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import IngestFilesWorkflow, UpdateFilesWorkflow
from ..services.ingestion_service import IngestionService
from .base_router import BaseRouter, RunType

logger = logging.getLogger(__name__)


class IngestionRouter(BaseRouter):
    def __init__(
        self,
        service: IngestionService,
        run_type: RunType = RunType.INGESTION,
        orchestration_provider: Optional[OrchestrationProvider] = None,
    ):
        if not orchestration_provider:
            raise ValueError(
                "IngestionRouter requires an orchestration provider."
            )
        super().__init__(service, run_type, orchestration_provider)
        self.service: IngestionService = service

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            IngestFilesWorkflow(self.service)
        )
        self.orchestration_provider.register_workflow(
            UpdateFilesWorkflow(self.service)
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
            chunking_config: Optional[Json[ChunkingConfig]] = Form(
                None,
                description=ingest_files_descriptions.get("chunking_config"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Ingest files into the system.

            This endpoint supports multipart/form-data requests, enabling you to ingest files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access. More expansive collection permissioning is under development.
            """
            self._validate_chunking_config(chunking_config)
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

            messages = []
            for it, file_data in enumerate(file_datas):
                content_length = len(file_data["content"])
                file_content = BytesIO(base64.b64decode(file_data["content"]))

                file_data.pop("content", None)
                document_id = (
                    document_ids[it]
                    if document_ids
                    else generate_user_document_id(
                        file_data["filename"], auth_user.id
                    )
                )

                workflow_input = {
                    "file_data": file_data,
                    "document_id": str(document_id),
                    "metadata": metadatas[it] if metadatas else None,
                    "chunking_config": (
                        chunking_config.model_dump_json()
                        if chunking_config
                        else None
                    ),
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

                task_id = r2r_hatchet.admin.run_workflow(
                    "ingest-file",
                    {"request": workflow_input},
                    options={
                        "additional_metadata": {
                            "document_id": str(document_id),
                        }
                    },
                )

                messages.append(
                    {
                        "message": "Ingestion task queued successfully.",
                        "task_id": str(task_id),
                        "document_id": str(document_id),
                    }
                )
            return messages

        @self.router.post(
            "/retry_ingest_files",
            openapi_extra=ingest_files_extras.get("openapi_extra"),
        )
        @self.base_endpoint
        async def retry_ingest_files(
            document_ids: list[UUID] = Form(
                ...,
                description=ingest_files_descriptions.get("document_ids"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Retry the ingestion of files into the system.

            This endpoint allows you to retry the ingestion of files that have previously failed to ingest into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only retry the ingestion of their own files. More expansive collection permissioning is under development.
            """
            if not auth_user.is_superuser:
                documents_overview = await self.service.providers.database.relational.get_documents_overview(
                    filter_document_ids=document_ids,
                    filter_user_ids=[auth_user.id],
                )
                if len(documents_overview) != len(document_ids):
                    raise R2RException(
                        status_code=404,
                        message="One or more documents not found.",
                    )

            # FIXME:  This is throwing an aiohttp.client_exceptions.ClientConnectionError: Cannot connect to host localhost:8080 ssl:default… can we whitelist the host?
            workflow_list = await r2r_hatchet.rest.workflow_run_list()

            # TODO: we want to extract the hatchet run ids for the document ids, and then retry them

            return {
                "message": "Retry tasks queued successfully.",
                "task_ids": [str(task_id) for task_id in workflow_list],
                "document_ids": [str(doc_id) for doc_id in document_ids],
            }

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
            chunking_config: Optional[Json[ChunkingConfig]] = Form(
                None,
                description=ingest_files_descriptions.get("chunking_config"),
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUpdateResponse:
            """
            Update existing files in the system.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only update their own files. More expansive collection permissioning is under development.
            """
            self._validate_chunking_config(chunking_config)
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
                    else generate_user_document_id(
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
                "chunking_config": (
                    chunking_config.model_dump_json()
                    if chunking_config
                    else None
                ),
                "user": auth_user.model_dump_json(),
                "is_update": True,
            }

            task_id = r2r_hatchet.admin.run_workflow(
                "update-files", {"request": workflow_input}
            )

            return {
                "message": "Update task queued successfully.",
                "task_id": str(task_id),
                "document_ids": workflow_input["document_ids"],
            }

    @staticmethod
    def _validate_chunking_config(chunking_config):
        from ..assembly.factory import R2RProviderFactory

        if chunking_config:
            chunking_config.validate()
            R2RProviderFactory.create_chunking_provider(chunking_config)
        else:
            logger.info("No chunking config override provided. Using default.")

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
