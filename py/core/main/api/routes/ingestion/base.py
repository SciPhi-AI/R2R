import json
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

import yaml
from fastapi import Depends, File, Form, UploadFile
from pydantic import Json

from core.base import ChunkingConfig, R2RException
from core.base.api.models.ingestion.responses import WrappedIngestionResponse
from core.base.utils import generate_user_document_id

from ....assembly.factory import R2RProviderFactory
from ....engine import R2REngine
from ..base_router import BaseRouter, RunType

logger = logging.getLogger(__name__)


class IngestionRouter(BaseRouter):
    def __init__(
        self, engine: R2REngine, run_type: RunType = RunType.INGESTION
    ):
        super().__init__(engine, run_type)
        self.openapi_extras = self.load_openapi_extras()
        self.setup_routes()

    def load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "ingestion_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def setup_routes(self):
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
            files: List[UploadFile] = File(
                ..., description=ingest_files_descriptions.get("files")
            ),
            document_ids: Optional[Json[list[UUID]]] = Form(
                None,
                description=ingest_files_descriptions.get("document_ids"),
            ),
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            chunking_settings: Optional[Json[ChunkingConfig]] = Form(
                None,
                description=ingest_files_descriptions.get("chunking_settings"),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Ingest files into the system.

            This endpoint supports multipart/form-data requests, enabling you to ingest files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access. More expansive group permissioning is under development.
            """
            chunking_provider = None
            if chunking_settings:
                chunking_settings.validate()
                chunking_provider = (
                    R2RProviderFactory.create_chunking_provider(
                        chunking_settings
                    )
                )
            else:
                logger.info(
                    "No chunking config override provided. Using default."
                )

            # Check if the user is a superuser
            is_superuser = auth_user and auth_user.is_superuser

            # Handle user management logic at the request level
            if not auth_user:
                for metadata in metadatas or []:
                    if "user_id" in metadata and (
                        not is_superuser
                        and metadata["user_id"] != str(auth_user.id)
                    ):
                        raise R2RException(
                            status_code=403,
                            message="Non-superusers cannot set user_id in metadata.",
                        )

                # If user is not a superuser, set user_id in metadata
                metadata["user_id"] = str(auth_user.id)

            ingestion_result = await self.engine.aingest_files(
                files=files,
                metadatas=metadatas,
                document_ids=document_ids,
                user=auth_user,
                chunking_provider=chunking_provider,
            )

            # If superuser, assign documents to groups
            if is_superuser:
                for idx, metadata in enumerate(metadatas or []):
                    if "group_ids" in metadata:
                        document_id = ingestion_result["processed_documents"][
                            idx
                        ]
                        for group_id in metadata["group_ids"]:
                            await self.engine.management_service.aassign_document_to_group(
                                document_id, group_id
                            )

            return ingestion_result

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
            files: List[UploadFile] = File(
                ..., description=update_files_descriptions.get("files")
            ),
            document_ids: Optional[Json[list[UUID]]] = Form(
                None,
                description=ingest_files_descriptions.get("document_ids"),
            ),
            metadatas: Optional[Json[list[dict]]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            chunking_settings: Optional[Json[ChunkingConfig]] = Form(
                None,
                description=ingest_files_descriptions.get("chunking_settings"),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Update existing files in the system.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.




            A valid user authentication token is required to access this endpoint, as regular users can only update their own files. More expansive group permissioning is under development.
            """

            chunking_provider = None
            if chunking_settings:
                config = ChunkingConfig(**chunking_settings)
                chunking_provider = (
                    R2RProviderFactory.create_chunking_provider(config)
                )

            return await self.engine.aupdate_files(
                files=files,
                metadatas=metadatas,
                document_ids=document_ids,
                chunking_provider=chunking_provider,
                user=auth_user,
            )
