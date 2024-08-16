import json
import logging
import uuid
from typing import List, Optional

from fastapi import Depends, File, Form, UploadFile
from fastapi.openapi.models import Example

from r2r.base import ChunkingConfig, R2RException
from r2r.base.api.models.ingestion.responses import WrappedIngestionResponse

from ....assembly.factory import R2RProviderFactory
from ....engine import R2REngine
from ..base_router import BaseRouter

logger = logging.getLogger(__name__)


class IngestionRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):

        # Note, we use the following verbose input parameters because FastAPI struggles to handle `File` input and `Body` inputs
        # at the same time. Therefore, we must ues `Form` inputs for the metadata, document_ids, and versions inputs.
        @self.router.post(
            "/ingest_files",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """from r2r import R2RClient

client = R2RClient("http://localhost:8000")
# when using auth, do client.login(...)

result = client.ingest_files(
    files=["pg_essay_1.html", "got.txt"],
    metadatas=[{"metadata_1":"some random metadata"}, {"metadata_2": "some other random metadata"}],
    document_ids=None,
    versions=None
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """curl -X POST "https://api.example.com/ingest_files" \\
  -H "Content-Type: multipart/form-data" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -F "file=@pg_essay_1.html;type=text/html" \\
  -F "file=@got.txt;type=text/plain" \\
  -F 'metadatas=[{},{}]' \\
  -F 'document_ids=null' \\
  -F 'versions=null'
""",
                    },
                ]
            },
            responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "example": {
                                "results": {
                                    "processed_documents": [
                                        {
                                            "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                            "title": "pg_essay_1.html",
                                        },
                                        {
                                            "id": "716fea3a-826b-5b27-8e59-ffbd1a35455a",
                                            "title": "got.txt",
                                        },
                                    ],
                                    "failed_documents": [],
                                    "skipped_documents": [],
                                }
                            }
                        }
                    },
                },
                422: {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": [
                                    {
                                        "message": "All documents were already successfully processed",
                                        "error_type": "R2RException",
                                    }
                                ]
                            }
                        }
                    },
                },
            },
            response_model=WrappedIngestionResponse,
        )
        @self.base_endpoint
        async def ingest_files_app(
            files: List[UploadFile] = File(
                ...,
                description="A list of file paths to be ingested. E.g. `file1.txt`, `file2.txt`",
            ),
            metadatas: Optional[str] = Form(
                None,
                description="JSON string containing metadata for each file, e.g. `{'title': 'Document 1', 'author': 'John Doe'}`",
                examples=[
                    Example(
                        summary="Sample metadata",
                        description="JSON string with metadata for two documents",
                        value='[{"title": "Document 1", "author": "John Doe"}, {"title": "Document 2", "author": "Jane Smith"}]',
                    )
                ],
            ),
            document_ids: Optional[str] = Form(
                None,
                description="Comma-separated list of document IDs, e.g. `3e157b3a-8469-51db-90d9-52e7d896b49b,223e4567-e89b-12d3-a456-426614174000`",
                examples=[
                    Example(
                        summary="Sample document IDs",
                        description="Comma-separated list of document IDs",
                        value="3e157b3a-8469-51db-90d9-52e7d896b49b,223e4567-e89b-12d3-a456-426614174000",
                    )
                ],
            ),
            versions: Optional[str] = Form(
                None,
                description="Comma-separated list of versions, e.g. `1.0,1.1`",
                examples=[
                    Example(
                        summary="Sample versions",
                        description="Comma-separated list of versions",
                        value="1.0,1.1",
                    )
                ],
            ),
            chunking_config_override: Optional[str] = Form(
                None,
                description="JSON string for chunking configuration override",
                examples=[
                    Example(
                        summary="Sample chunking config override",
                        description="JSON string for chunking configuration override",
                        value='{"chunk_size": 1000, "chunk_overlap": 200}',
                    )
                ],
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            """
            Ingest files into the system.

            This endpoint supports multipart/form-data requests, enabling you to update files along with their inside of R2R. A valid user authentication token is required to access this endpoint. Regular users can only update documents they have permission to access.
            """
            try:
                parsed_data = self.parse_ingest_files_form_data(
                    metadatas, document_ids, versions, chunking_config_override
                )
            except R2RException as e:
                raise e

            kwargs = {}
            if chunking_config_override:
                config = ChunkingConfig(**chunking_config_override)
                config.validate()
                kwargs["chunking_provider"] = (
                    R2RProviderFactory.create_chunking_provider(config)
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
                    if "user_id" in metadata:
                        if not is_superuser and metadata["user_id"] != str(
                            auth_user.id
                        ):
                            raise R2RException(
                                status_code=403,
                                message="Non-superusers cannot set user_id in metadata.",
                            )
                    if "group_ids" in metadata:
                        if not is_superuser:
                            raise R2RException(
                                status_code=403,
                                message="Non-superusers cannot set group_ids in metadata.",
                            )

                # If user is not a superuser, set user_id in metadata
                metadata["user_id"] = str(auth_user.id)

            ingestion_result = await self.engine.aingest_files(
                files=files,
                metadatas=parsed_data["metadatas"],
                document_ids=parsed_data["document_ids"],
                versions=parsed_data["versions"],
                user=auth_user,
                **kwargs,
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

        @self.router.post(
            "/update_files",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """from r2r import R2RClient

client = R2RClient("http://localhost:8000")
# when using auth, do client.login(...)

result = client.update_files(
    files=["pg_essay_1_v2.txt"],
    document_ids=["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"]
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """curl -X POST "https://api.example.com/update_files" \\
  -H "Content-Type: multipart/form-data" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -F "file=@pg_essay_1_v2.txt;type=text/plain" \\
  -F 'document_ids=["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"]'
""",
                    },
                ]
            },
            responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "example": {
                                "results": {
                                    "processed_documents": [
                                        {
                                            "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                            "title": "pg_essay_1_v2.html",
                                        },
                                    ],
                                    "failed_documents": [],
                                    "skipped_documents": [],
                                }
                            }
                        }
                    },
                },
                422: {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "example": {
                                "detail": [
                                    {
                                        "message": "Document 'b4ac4dd6-5f27-596e-a55b-7cf242ca30aa' does not exist.",
                                        "error_type": "R2RException",
                                    }
                                ]
                            }
                        }
                    },
                },
            },
            response_model=WrappedIngestionResponse,
        )
        @self.base_endpoint
        async def update_files_app(
            files: List[UploadFile] = File(
                ...,
                description="List of files to update",
            ),
            metadatas: Optional[str] = Form(
                None,
                description="JSON string containing updated metadata for each file",
                examples=[
                    Example(
                        summary="Sample updated metadata",
                        description="JSON string with updated metadata for two documents",
                        value='[{"title": "Updated Document 1", "version": "1.1"}, {"title": "Updated Document 2", "version": "1.2"}]',
                    )
                ],
            ),
            document_ids: Optional[str] = Form(
                None,
                description="Comma-separated list of document IDs to update",
                examples=[
                    Example(
                        summary="Sample document IDs",
                        description="Comma-separated list of document IDs to update",
                        value="3e157b3a-8469-51db-90d9-52e7d896b49b,223e4567-e89b-12d3-a456-426614174000",
                    )
                ],
            ),
            chunking_config_override: Optional[str] = Form(
                None,
                description="JSON string for chunking configuration override",
                examples=[
                    Example(
                        summary="Sample chunking config override",
                        description="JSON string for chunking configuration override",
                        value='{"chunk_size": 1200, "chunk_overlap": 250}',
                    )
                ],
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            """
            Update existing files in the system.

            This endpoint supports multipart/form-data requests, enabling you to update files along with their inside of R2R. A valid user authentication token is required to access this endpoint. Regular users can only update documents they have permission to access.
            """

            try:
                parsed_data = self.parse_update_files_form_data(
                    metadatas, document_ids, chunking_config_override
                )
            except R2RException as e:
                raise e

            chunking_config_override = None
            if chunking_config_override:
                config = ChunkingConfig(**chunking_config_override)
                chunking_config_override = (
                    R2RProviderFactory.create_chunking_provider(config)
                )

            return await self.engine.aupdate_files(
                files=files,
                metadatas=parsed_data["metadatas"],
                document_ids=parsed_data["document_ids"],
                chunking_config_override=chunking_config_override,
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
                    uuid.UUID(doc_id) for doc_id in parsed_document_ids
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
            )
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e))
        except Exception as e:
            raise R2RException(
                status_code=400, message=f"Error processing form data: {e}"
            )

    @staticmethod
    def parse_update_files_form_data(
        metadatas: Optional[str],
        document_ids: str,
        chunking_config_override: Optional[str],
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

            if not document_ids or document_ids == "null":
                raise ValueError("document_ids is required and cannot be null")

            parsed_document_ids = json.loads(document_ids)
            if not isinstance(parsed_document_ids, list):
                raise ValueError("document_ids must be a list")
            parsed_document_ids = [
                uuid.UUID(doc_id) for doc_id in parsed_document_ids
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
            )
        except ValueError as e:
            raise R2RException(status_code=400, message=str(e))
        except Exception as e:
            raise R2RException(
                status_code=400, message=f"Error processing form data: {e}"
            )
