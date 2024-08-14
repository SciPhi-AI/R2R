from fastapi import Depends, File, UploadFile

from r2r.base import ChunkingConfig, R2RException
from r2r.main.api.routes.ingestion.requests import (
    R2RIngestFilesRequest,
    R2RUpdateFilesRequest,
)

from ....assembly.factory import R2RProviderFactory
from ....engine import R2REngine
from ....services.ingestion_service import IngestionService
from ..base_router import BaseRouter


class IngestionRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):

        @self.router.post("/ingest_files")
        @self.base_endpoint
        async def ingest_files_app(
            files: list[UploadFile] = File(...),
            request: R2RIngestFilesRequest = Depends(
                IngestionService.parse_ingest_files_form_data
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            kwargs = {}
            if request.chunking_config_override:
                config = ChunkingConfig(**request.chunking_config_override)
                config.validate()
                kwargs["chunking_provider"] = (
                    R2RProviderFactory.create_chunking_provider(config)
                )
            else:
                print("No chunking config override provided. Using default.")

            # Check if the user is a superuser
            is_superuser = auth_user and auth_user.is_superuser

            # Handle user management logic at the request level
            if auth_user:
                for metadata in request.metadatas or []:
                    if "user_id" in metadata:
                        if not is_superuser and metadata["user_id"] != str(
                            auth_user.id
                        ):
                            raise R2RException(
                                status_code=403,
                                message="Non-superusers cannot set user_id in metadata.",
                            )
                    else:
                        metadata["user_id"] = str(auth_user.id)

            # Remove group_ids from non-superusers
            if not is_superuser:
                for metadata in request.metadatas or []:
                    metadata.pop("group_ids", None)

            ingestion_result = await self.engine.aingest_files(
                files=files,
                metadatas=request.metadatas,
                document_ids=request.document_ids,
                versions=request.versions,
                user=auth_user,
                **kwargs
            )

            # If superuser, assign documents to groups
            if is_superuser:
                for idx, metadata in enumerate(request.metadatas or []):
                    if "group_ids" in metadata:
                        document_id = ingestion_result["processed_documents"][
                            idx
                        ]
                        for group_id in metadata["group_ids"]:
                            await self.engine.management_service.aassign_document_to_group(
                                document_id, group_id
                            )

            return ingestion_result

        @self.router.post("/update_files")
        @self.base_endpoint
        async def update_files_app(
            files: list[UploadFile] = File(...),
            request: R2RUpdateFilesRequest = Depends(
                IngestionService.parse_update_files_form_data
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            chunking_config_override = None
            if request.chunking_config_override:
                config = ChunkingConfig(**request.chunking_config_override)
                chunking_config_override = (
                    R2RProviderFactory.create_chunking_provider(config)
                )

            return await self.engine.aupdate_files(
                files=files,
                metadatas=request.metadatas,
                document_ids=request.document_ids,
                chunking_config_override=chunking_config_override,
                user=auth_user,
            )
