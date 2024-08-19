import json
import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

import yaml
from fastapi import Depends, File, Form, UploadFile

from r2r.base import ChunkingConfig, R2RException
from r2r.base.api.models.ingestion.responses import WrappedIngestionResponse
from r2r.base.utils import generate_user_document_id

from ....assembly.factory import R2RProviderFactory
from ....engine import R2REngine
from ..base_router import BaseRouter

logger = logging.getLogger(__name__)


class IngestionRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.openapi_extras = self.load_openapi_extras()
        self.setup_routes()

    def load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "ingestion_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def setup_routes(self):
        # Note, we use the following verbose input parameters because FastAPI struggles to handle `File` input and `Body` inputs
        # at the same time. Therefore, we must ues `Form` inputs for the metadata, document_ids, and versions inputs.
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
            document_ids: Optional[list[str]] = Form(
                None,
                description=ingest_files_descriptions.get("document_ids"),
            ),
            versions: Optional[list[str]] = Form(
                None, description=ingest_files_descriptions.get("versions")
            ),
            metadatas: Optional[list[dict]] = Form(
                None, description=ingest_files_descriptions.get("metadatas")
            ),
            chunking_config_override: Optional[ChunkingConfig] = Form(
                None,
                description=ingest_files_descriptions.get(
                    "chunking_config_override"
                ),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Ingest files into the system.

            This endpoint supports multipart/form-data requests, enabling you to ingest files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access. More expansive group permissioning is under development.
            """
            try:
                parsed_data = self.parse_ingest_files_form_data(
                    metadatas, document_ids, versions, chunking_config_override
                )
            except R2RException as e:
                raise e

            chunking_provider = None
            if chunking_config_override:
                chunking_config_override.validate()
                chunking_provider = (
                    R2RProviderFactory.create_chunking_provider(
                        chunking_config_override
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
                metadatas=parsed_data["metadatas"],
                document_ids=parsed_data["document_ids"],
                versions=parsed_data["versions"],
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
            document_ids: Optional[list[str]] = Form(
                None, description=update_files_descriptions.get("document_ids")
            ),
            metadatas: Optional[list[dict]] = Form(
                None, description=update_files_descriptions.get("metadatas")
            ),
            chunking_config_override: Optional[str] = Form(
                None,
                description=update_files_descriptions.get(
                    "chunking_config_override"
                ),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Update existing files in the system.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.




            A valid user authentication token is required to access this endpoint, as regular users can only update their own files. More expansive group permissioning is under development.
            """

            try:
                parsed_data = self.parse_update_files_form_data(
                    metadatas,
                    document_ids,
                    chunking_config_override,
                    [file.filename for file in files],
                    auth_user.id,
                )
            except R2RException as e:
                raise e

            chunking_provider = None
            if chunking_config_override:
                config = ChunkingConfig(**chunking_config_override)
                chunking_provider = (
                    R2RProviderFactory.create_chunking_provider(config)
                )

            return await self.engine.aupdate_files(
                files=files,
                metadatas=parsed_data["metadatas"],
                document_ids=parsed_data["document_ids"],
                chunking_provider=chunking_provider,
                user=auth_user,
            )

    @staticmethod
    def parse_ingest_files_form_data(
        metadatas: Optional[str],
        document_ids: Optional[str],
        versions: Optional[str],
        chunking_config_override: Optional[str],
    ) -> dict:
        try:
            parsed_metadatas = (
                json.loads(metadatas)
                if metadatas and metadatas != "null"
                else None
            )
            if parsed_metadatas is not None and not isinstance(
                parsed_metadatas, list
            ):
                raise ValueError("metadatas must be a list of dictionaries")

            parsed_document_ids = (
                json.loads(document_ids)
                if document_ids and document_ids != "null"
                else None
            )
            if parsed_document_ids is not None:
                parsed_document_ids = [
                    UUID(doc_id) for doc_id in parsed_document_ids
                ]

            parsed_versions = (
                json.loads(versions)
                if versions and versions != "null"
                else None
            )

            parsed_chunking_config = (
                json.loads(chunking_config_override)
                if chunking_config_override
                and chunking_config_override != "null"
                else None
            )

            return {
                "metadatas": parsed_metadatas,
                "document_ids": parsed_document_ids,
                "versions": parsed_versions,
                "chunking_config_override": parsed_chunking_config,
            }
        except json.JSONDecodeError as e:
            raise R2RException(
                status_code=400, message=f"Invalid JSON in form data: {e}"
            ) from e
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e)) from e
        except Exception as e:
            raise R2RException(
                status_code=400, message=f"Error processing form data: {e}"
            ) from e

    @staticmethod
    def parse_update_files_form_data(
        metadatas: Optional[list[dict]],
        document_ids: Optional[list[str]],
        chunking_config_override: Optional[str],
        filenames: list[str],
        user_id: str,
    ):
        try:
            parsed_metadatas = (
                json.loads(metadatas)
                if metadatas and metadatas != "null"
                else None
            )
            if parsed_metadatas is not None and not isinstance(
                parsed_metadatas, list
            ):
                raise ValueError("metadatas must be a list of dictionaries")

            parsed_document_ids = (
                json.loads(document_ids)
                if document_ids and document_ids != "null"
                else None
            )
            if parsed_document_ids is not None:
                parsed_document_ids = [
                    UUID(doc_id) for doc_id in parsed_document_ids
                ]
            else:
                parsed_document_ids = [
                    generate_user_document_id(filename, UUID(user_id))
                    for filename in filenames
                ]

            parsed_chunking_config = (
                json.loads(chunking_config_override)
                if chunking_config_override
                and chunking_config_override != "null"
                else None
            )

            return {
                "metadatas": parsed_metadatas,
                "document_ids": parsed_document_ids,
                "chunking_config_override": parsed_chunking_config,
            }
        except json.JSONDecodeError as e:
            raise R2RException(
                status_code=400, message=f"Invalid JSON in form data: {e}"
            ) from e
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e)) from e
        except Exception as e:
            raise R2RException(
                status_code=400, message=f"Error processing form data: {e}"
            ) from e
