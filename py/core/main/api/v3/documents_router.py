import base64
import json
import logging
import mimetypes
import textwrap
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import Depends, File, Form, Path, Query, UploadFile, Body
from fastapi.responses import StreamingResponse
from pydantic import Json

from core.base import R2RException, RunType, generate_document_id
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
    WrappedIngestionResponse,
    WrappedKGCreationResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from core.base.abstractions import (
    Entity,
    KGCreationSettings,
    KGRunType,
    Relationship,
    GraphBuildSettings,
)

from core.utils import update_settings_from_dict

from .base_router import BaseRouterV3

logger = logging.getLogger()


class DocumentsRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.INGESTION,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post(
            "/documents",
            status_code=202,
            summary="Create a new document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.create(
                                file_path="pg_essay_1.html",
                                metadata={"metadata_1":"some random metadata"},
                                id=None
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.create({
                                    file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
                                    metadata: { title: "marmeladov.txt" },
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents create /path/to/file.txt
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/documents" \\
                            -H "Content-Type: multipart/form-data" \\
                            -H "Authorization: Bearer YOUR_API_KEY" \\
                            -F "file=@pg_essay_1.html;type=text/html" \\
                            -F 'metadata={}' \\
                            -F 'id=null'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_document(
            file: Optional[UploadFile] = File(
                None,
                description="The file to ingest. Either a file or content must be provided, but not both.",
            ),
            content: Optional[str] = Form(
                None,
                description="The text content to ingest. Either a file or content must be provided, but not both.",
            ),
            id: Optional[UUID] = Form(
                None,
                description="The ID of the document. If not provided, a new ID will be generated.",
            ),
            collection_ids: Optional[list[str]] = Form(
                None,
                description="Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.",
            ),
            metadata: Optional[Json[dict]] = Form(
                None,
                description="Metadata to associate with the document, such as title, description, or custom fields.",
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description="An optional dictionary to override the default chunking configuration for the ingestion process. If not provided, the system will use the default server-side chunking configuration.",
            ),
            run_with_orchestration: Optional[bool] = Form(
                True,
                description="Whether or not ingestion runs with orchestration, default is `True`. When set to `False`, the ingestion process will run synchronous and directly return the result.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Creates a new Document object from an input file or text content. The document will be processed
            to create chunks for vector indexing and search.

            Either a file or text content must be provided, but not both. Regular users can only create
            documents for themselves, while superusers can create documents for any user.

            The ingestion process runs asynchronously and its progress can be tracked using the returned
            task_id.
            """
            if not file and not content:
                raise R2RException(
                    status_code=422,
                    message="Either a file or content must be provided.",
                )
            if file and content:
                raise R2RException(
                    status_code=422,
                    message="Both a file and content cannot be provided.",
                )
            # Check if the user is a superuser
            metadata = metadata or {}
            if not auth_user.is_superuser:
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

            if file:
                file_data = await self._process_file(file)
                content_length = len(file_data["content"])
                file_content = BytesIO(base64.b64decode(file_data["content"]))

                file_data.pop("content", None)
                document_id = id or generate_document_id(
                    file_data["filename"], auth_user.id
                )
            elif content:
                content_length = len(content)
                file_content = BytesIO(content.encode("utf-8"))
                document_id = id or generate_document_id(content, auth_user.id)
                file_data = {
                    "filename": "N/A",
                    "content_type": "text/plain",
                }
            else:
                raise R2RException(
                    status_code=422,
                    message="Either a file or content must be provided.",
                )

            collection_uuids = None
            if collection_ids:
                try:
                    collection_uuids = [UUID(cid) for cid in collection_ids]
                except ValueError:
                    raise R2RException(
                        status_code=422,
                        message="Collection IDs must be valid UUIDs.",
                    )

            workflow_input = {
                "file_data": file_data,
                "document_id": str(document_id),
                "collection_ids": collection_uuids,
                "metadata": metadata,
                "ingestion_config": ingestion_config,
                "user": auth_user.model_dump_json(),
                "size_in_bytes": content_length,
                "is_update": False,
            }

            file_name = file_data["filename"]
            await self.providers.database.store_file(
                document_id,
                file_name,
                file_content,
                file_data["content_type"],
            )
            if run_with_orchestration:
                raw_message: dict[str, str | None] = await self.orchestration_provider.run_workflow(  # type: ignore
                    "ingest-files",
                    {"request": workflow_input},
                    options={
                        "additional_metadata": {
                            "document_id": str(document_id),
                        }
                    },
                )
                raw_message["document_id"] = str(document_id)
                return raw_message  # type: ignore
            else:
                logger.info(
                    f"Running ingestion without orchestration for file {file_name} and document_id {document_id}."
                )
                # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(
                    self.services["ingestion"]
                )
                await simple_ingestor["ingest-files"](workflow_input)
                return {  # type: ignore
                    "message": "Ingestion task completed successfully.",
                    "document_id": str(document_id),
                    "task_id": None,
                }

        @self.router.post(
            "/documents/{id}",
            summary="Update a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.update(
                                file_path="pg_essay_1.html",
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.update({
                                    file: { path: "pg_essay_1.html", name: "pg_essay_1.html" },
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents update /path/to/file.txt --id=9fbe403b-c11c-5aae-8ade-ef22980c3ad1
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/document/9fbe403b-c11c-5aae-8ade-ef22980c3ad1"  \\
                            -H "Content-Type: multipart/form-data"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"  \\
                            -F "file=@pg_essay_1.html;type=text/plain"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_document(  # type: ignore
            file: Optional[UploadFile] = File(
                None,
                description="The file to ingest. Either a file or content must be provided, but not both.",
            ),
            content: Optional[str] = Form(
                None,
                description="The text content to ingest. Either a file or content must be provided, but not both.",
            ),
            id: UUID = Path(
                ...,
                description="The ID of the document. If not provided, a new ID will be generated.",
            ),
            metadata: Optional[list[dict]] = Form(
                None,
                description="Metadata to associate with the document, such as title, description, or custom fields.",
            ),
            ingestion_config: Optional[Json[dict]] = Form(
                None,
                description="An optional dictionary to override the default chunking configuration for the ingestion process. If not provided, the system will use the default server-side chunking configuration.",
            ),
            run_with_orchestration: Optional[bool] = Form(
                True,
                description="Whether or not ingestion runs with orchestration, default is `True`. When set to `False`, the ingestion process will run synchronous and directly return the result.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedIngestionResponse:
            """
            Updates an existing document with new content and/or metadata. This will trigger
            reprocessing of the document's chunks and knowledge graph data.

            Either a new file or text content must be provided, but not both. The update process
            runs asynchronously and its progress can be tracked using the returned task_id.

            Metadata can be updated to change the document's title, description, or other fields. These changes are additive w.r.t. the existing metadata, but for chunks and knowledge graph data, the update is a full replacement.

            Regular users can only update their own documents. Superusers can update any document.
            All previous document versions are preserved in the system.
            """
            if file and content:
                raise R2RException(
                    status_code=422,
                    message="Both a file and content cannot be provided.",
                )

            if (not file and not content) and metadata:
                pass
                # metadata update only
                ## TODO - Uncomment after merging in `main`
                # workflow_input = {
                #     "document_id": str(id),
                #     "metadata": metadata,
                #     "user": auth_user.model_dump_json(),
                # }

                # logger.info(
                #     "Running document metadata update without orchestration."
                # )
                # from core.main.orchestration import simple_ingestion_factory

                # simple_ingestor = simple_ingestion_factory(self.service)
                # await simple_ingestor["update-document-metadata"](
                #     workflow_input
                # )
                # return {  # type: ignore
                #     "message": "Update metadata task completed successfully.",
                #     "id": str(document_id),
                #     "task_id": None,
                # }

            else:
                metadata = metadata or {}  # type: ignore

                # Check if the user is a superuser
                if not auth_user.is_superuser:
                    if (
                        metadata is not None
                        and "user_id" in metadata
                        and metadata["user_id"] != str(auth_user.id)  # type: ignore
                    ):
                        raise R2RException(
                            status_code=403,
                            message="Non-superusers cannot set user_id in metadata.",
                        )
                    metadata["user_id"] = str(auth_user.id)  # type: ignore

                if file:
                    file_data = await self._process_file(file)
                    content_length = len(file_data["content"])
                    file_content = BytesIO(
                        base64.b64decode(file_data["content"])
                    )
                    file_data.pop("content", None)
                elif content:
                    content_length = len(content)
                    file_content = BytesIO(content.encode("utf-8"))
                    file_data = {
                        "filename": f"N/A",
                        "content_type": "text/plain",
                    }
                else:
                    raise R2RException(
                        status_code=422,
                        message="Either a file or content must be provided.",
                    )
                await self.providers.database.store_file(
                    id,
                    file_data["filename"],
                    file_content,
                    file_data["content_type"],
                )

                workflow_input = {
                    "file_datas": [file_data],
                    "document_ids": [str(id)],
                    "metadatas": [metadata],
                    "ingestion_config": ingestion_config,
                    "user": auth_user.model_dump_json(),
                    "file_sizes_in_bytes": [content_length],
                    "is_update": False,
                    "user": auth_user.model_dump_json(),
                    "is_update": True,
                }

                if run_with_orchestration:
                    raw_message: dict[str, str | None] = await self.orchestration_provider.run_workflow(  # type: ignore
                        "update-files", {"request": workflow_input}, {}
                    )
                    raw_message["message"] = "Update task queued successfully."
                    raw_message["document_id"] = workflow_input[
                        "document_ids"
                    ][0]

                    return raw_message  # type: ignore
                else:
                    logger.info("Running update without orchestration.")
                    # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                    from core.main.orchestration import (
                        simple_ingestion_factory,
                    )

                    simple_ingestor = simple_ingestion_factory(
                        self.services["ingestion"]
                    )
                    await simple_ingestor["update-files"](workflow_input)
                    return {  # type: ignore
                        "message": "Update task completed successfully.",
                        "document_id": workflow_input["document_ids"],
                        "task_id": None,
                    }

        @self.router.get(
            "/documents",
            summary="List documents",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list(
                                limit=10,
                                offset=0
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.list({
                                    limit: 10,
                                    offset: 0,
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents create /path/to/file.txt
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/documents"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_documents(
            ids: list[str] = Query(
                [],
                description="A list of document IDs to retrieve. If not provided, all documents will be returned.",
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDocumentsResponse:
            """
            Returns a paginated list of documents the authenticated user has access to.

            Results can be filtered by providing specific document IDs. Regular users will only see
            documents they own or have access to through collections. Superusers can see all documents.

            The documents are returned in order of last modification, with most recent first.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            filter_collection_ids = (
                None if auth_user.is_superuser else auth_user.collection_ids
            )

            document_uuids = [UUID(document_id) for document_id in ids]
            documents_overview_response = await self.services[
                "management"
            ].documents_overview(
                user_ids=requesting_user_id,
                collection_ids=filter_collection_ids,
                document_ids=document_uuids,
                offset=offset,
                limit=limit,
            )

            return (  # type: ignore
                documents_overview_response["results"],
                {
                    "total_entries": documents_overview_response[
                        "total_entries"
                    ]
                },
            )

        @self.router.get(
            "/documents/{id}",
            summary="Retrieve a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.retrieve(
                            id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.retrieve({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents retrieve 9fbe403b-c11c-5aae-8ade-ef22980c3ad1
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/documents/9fbe403b-c11c-5aae-8ade-ef22980c3ad1"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_document(
            id: UUID = Path(
                ...,
                description="The ID of the document to retrieve.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDocumentResponse:
            """
            Retrieves detailed information about a specific document by its ID.

            This endpoint returns the document's metadata, status, and system information. It does not
            return the document's content - use the `/documents/{id}/download` endpoint for that.

            Users can only retrieve documents they own or have access to through collections.
            Superusers can retrieve any document.
            """
            request_user_ids = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            filter_collection_ids = (
                None if auth_user.is_superuser else auth_user.collection_ids
            )

            documents_overview_response = await self.services[
                "management"
            ].documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
                user_ids=request_user_ids,
                collection_ids=filter_collection_ids,
                document_ids=[id],
                offset=0,
                limit=100,
            )
            results = documents_overview_response["results"]
            if len(results) == 0:
                raise R2RException("Document not found.", 404)

            return results[0]

        @self.router.get(
            "/documents/{id}/chunks",
            summary="List document chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list_chunks(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.listChunks({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents list-chunks 9fbe403b-c11c-5aae-8ade-ef22980c3ad1
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/documents/9fbe403b-c11c-5aae-8ade-ef22980c3ad1/chunks"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"\
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_chunks(
            id: UUID = Path(
                ...,
                description="The ID of the document to retrieve chunks for.",
            ),
            offset: Optional[int] = Query(
                0,
                ge=0,
                description="The offset of the first chunk to retrieve.",
            ),
            limit: Optional[int] = Query(
                100,
                ge=0,
                le=20_000,
                description="The maximum number of chunks to retrieve, up to 20,000.",
            ),
            include_vectors: Optional[bool] = Query(
                False,
                description="Whether to include vector embeddings in the response.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedChunksResponse:
            """
            Retrieves the text chunks that were generated from a document during ingestion.
            Chunks represent semantic sections of the document and are used for retrieval
            and analysis.

            Users can only access chunks from documents they own or have access to through
            collections. Vector embeddings are only included if specifically requested.

            Results are returned in chunk sequence order, representing their position in
            the original document.
            """
            list_document_chunks = await self.services[
                "management"
            ].list_document_chunks(id, offset, limit, include_vectors)

            if not list_document_chunks["results"]:
                raise R2RException(
                    "No chunks found for the given document ID.", 404
                )

            is_owner = str(
                list_document_chunks["results"][0].get("user_id")
            ) == str(auth_user.id)
            document_collections = await self.services[
                "management"
            ].collections_overview(
                offset=0,
                limit=-1,
                document_ids=[id],
            )

            user_has_access = (
                is_owner
                or set(auth_user.collection_ids).intersection(
                    {
                        ele.collection_id
                        for ele in document_collections["results"]
                    }
                )
                != set()
            )

            if not user_has_access and not auth_user.is_superuser:
                raise R2RException(
                    "Not authorized to access this document's chunks.", 403
                )

            return (  # type: ignore
                list_document_chunks["results"],
                {"total_entries": list_document_chunks["total_entries"]},
            )

        @self.router.get(
            "/documents/{id}/download",
            response_class=StreamingResponse,
            summary="Download document content",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.download(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.download({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/download"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_document_file(
            id: str = Path(..., description="Document ID"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> StreamingResponse:
            """
            Downloads the original file content of a document.

            For uploaded files, returns the original file with its proper MIME type.
            For text-only documents, returns the content as plain text.

            Users can only download documents they own or have access to through collections.
            """
            try:
                document_uuid = UUID(id)
            except ValueError:
                raise R2RException(
                    status_code=422, message="Invalid document ID format."
                )

            # Retrieve the document's information
            documents_overview_response = await self.services[
                "management"
            ].documents_overview(
                user_ids=None,
                collection_ids=None,
                document_ids=[document_uuid],
                offset=0,
                limit=1,
            )

            if not documents_overview_response["results"]:
                raise R2RException("Document not found.", 404)

            document = documents_overview_response["results"][0]

            is_owner = str(document.user_id) == str(auth_user.id)

            if not auth_user.is_superuser and not is_owner:
                document_collections = await self.services[
                    "management"
                ].collections_overview(
                    offset=0,
                    limit=-1,
                    document_ids=[document_uuid],
                )

                document_collection_ids = {
                    str(ele.id) for ele in document_collections["results"]
                }

                user_collection_ids = set(
                    str(cid) for cid in auth_user.collection_ids
                )

                has_collection_access = user_collection_ids.intersection(
                    document_collection_ids
                )

                if not has_collection_access:
                    raise R2RException(
                        "Not authorized to access this document.", 403
                    )

            file_tuple = await self.services["management"].download_file(
                document_uuid
            )
            if not file_tuple:
                raise R2RException(status_code=404, message="File not found.")

            file_name, file_content, file_size = file_tuple

            mime_type, _ = mimetypes.guess_type(file_name)
            if not mime_type:
                mime_type = "application/octet-stream"

            async def file_stream():
                chunk_size = 1024 * 1024  # 1MB
                while True:
                    data = file_content.read(chunk_size)
                    if not data:
                        break
                    yield data

            return StreamingResponse(
                file_stream(),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Content-Length": str(file_size),
                },
            )

        @self.router.delete(
            "/documents/{id}",
            summary="Delete a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.delete(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.delete({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents delete 9fbe403b-c11c-5aae-8ade-ef22980c3ad1
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa" \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_document_by_id(
            id: UUID = Path(..., description="Document ID"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Delete a specific document. All chunks corresponding to the document are deleted, and all other references to the document are removed.

            NOTE - Deletions do not yet impact the knowledge graph or other derived data. This feature is planned for a future release.
            """
            filters = {
                "$and": [
                    {"user_id": {"$eq": str(auth_user.id)}},
                    {"document_id": {"$eq": id}},
                ]
            }
            await self.services["management"].delete(filters=filters)
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.delete(
            "/documents/by-filter",
            summary="Delete documents by filter",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.documents.delete_by_filter(
                                filters='{"document_type": {"$eq": "text"}, "created_at": {"$lt": "2023-01-01T00:00:00Z"}}'
                            )
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/documents/by-filter?filters=%7B%22document_type%22%3A%7B%22%24eq%22%3A%22text%22%7D%2C%22created_at%22%3A%7B%22%24lt%22%3A%222023-01-01T00%3A00%3A00Z%22%7D%7D" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_document_by_filter(
            filters: str = Query(..., description="JSON-encoded filters"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Delete documents based on provided filters. Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`. Deletion requests are limited to a user's own documents.
            """

            try:
                filters_dict = json.loads(filters)
            except json.JSONDecodeError:
                raise R2RException(
                    status_code=422, message="Invalid JSON in filters"
                )

            if not isinstance(filters_dict, dict):
                raise R2RException(
                    status_code=422, message="Filters must be a JSON object"
                )

            filters_dict = {"$and": [{"$eq": str(auth_user.id)}, filters_dict]}

            for key, value in filters_dict.items():
                if not isinstance(value, dict):
                    raise R2RException(
                        status_code=422,
                        message=f"Invalid filter format for key: {key}",
                    )

            delete_bool = await self.services["management"].delete(
                filters=filters_dict
            )

            return GenericBooleanResponse(success=delete_bool)  # type: ignore

        @self.router.get(
            "/documents/{id}/collections",
            summary="List document collections",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.list_collections(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=10
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.documents.listCollections({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r documents list-collections 9fbe403b-c11c-5aae-8ade-ef22980c3ad1
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/documents/9fbe403b-c11c-5aae-8ade-ef22980c3ad1/collections"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_document_collections(
            id: str = Path(..., description="Document ID"),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionsResponse:
            """
            Retrieves all collections that contain the specified document. This endpoint is restricted
            to superusers only and provides a system-wide view of document organization.

            Collections are used to organize documents and manage access control. A document can belong
            to multiple collections, and users can access documents through collection membership.

            The results are paginated and ordered by collection creation date, with the most recently
            created collections appearing first.

            NOTE - This endpoint is only available to superusers, it will be extended to regular users in a future release.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get the collections belonging to a document.",
                    403,
                )

            collections_response = await self.services[
                "management"
            ].collections_overview(
                offset=offset,
                limit=limit,
                document_ids=[UUID(id)],  # Convert string ID to UUID
            )

            return collections_response["results"], {  # type: ignore
                "total_entries": collections_response["total_entries"]
            }


    @staticmethod
    async def _process_file(file):
        import base64

        content = await file.read()
        return {
            "filename": file.filename,
            "content": base64.b64encode(content).decode("utf-8"),
            "content_type": file.content_type,
        }
