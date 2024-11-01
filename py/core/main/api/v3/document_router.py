import base64
import json
import logging
import mimetypes
from io import BytesIO
from typing import Optional, Union
from uuid import UUID

from fastapi import Depends, File, Form, Path, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import Json

from core.base import R2RException, RunType, Workflow, generate_document_id
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3
from .chunk_responses import ChunkResponse
from .document_responses import (
    CollectionResponse,
    DocumentIngestionResponse,
    DocumentResponse,
)

logger = logging.getLogger()


class DocumentRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.INGESTION,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post("/documents")
        @self.base_endpoint
        async def ingest_document(
            file: Optional[UploadFile] = File(None),
            content: Optional[str] = Form(None),
            id: Optional[Json[UUID]] = Form(None),
            metadata: Optional[Json[dict]] = Form(None),
            ingestion_config: Optional[Json[dict]] = Form(None),
            run_with_orchestration: Optional[bool] = Form(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[DocumentIngestionResponse]:
            """
            Creates a new `Document` object from an input file or text content. Each document has corresponding `Chunk` objects which are used in vector indexing and search.

            This endpoint supports multipart/form-data requests.

            A valid user authentication token is required to access this endpoint, as regular users can only ingest files for their own access.
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
                document_id = document_id or generate_document_id(
                    file_data["filename"], auth_user.id
                )
            elif content:
                content_length = len(content)
                file_content = BytesIO(content.encode("utf-8"))
                document_id = document_id or generate_document_id(
                    content, auth_user.id
                )
                file_data = {
                    "filename": "N/A",
                    "content_type": "text/plain",
                }
            else:
                raise R2RException(
                    status_code=422,
                    message="Either a file or content must be provided.",
                )

            workflow_input = {
                "file_data": file_data,
                "document_id": str(document_id),
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
                    "document_id": str(id),
                    "task_id": None,
                }

        @self.router.post(
            "/documents/{id}",
        )
        @self.base_endpoint
        async def update_document(
            file: Optional[UploadFile] = File(None),
            content: Optional[str] = Form(None),
            id: UUID = Path(...),
            metadata: Optional[Json[dict]] = Form(None),
            ingestion_config: Optional[Json[dict]] = Form(None),
            run_with_orchestration: Optional[bool] = Form(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[DocumentIngestionResponse]:
            """
            Ingests updated files into R2R, updating the corresponding `Document` and `Chunk` objects from previous ingestion.

            This endpoint supports multipart/form-data requests, enabling you to update files and their associated metadatas into R2R.

            A valid user authentication token is required to access this endpoint, as regular users can only update their own files.
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
            metadata = metadata or {}  # type: ignore

            # Check if the user is a superuser
            if not auth_user.is_superuser:
                if "user_id" in metadata and metadata["user_id"] != str(
                    auth_user.id
                ):
                    raise R2RException(
                        status_code=403,
                        message="Non-superusers cannot set user_id in metadata.",
                    )
                metadata["user_id"] = str(auth_user.id)

            if file:
                file_data = await self._process_file(file)
                content_length = len(file_data["content"])
                file_content = BytesIO(base64.b64decode(file_data["content"]))
                file_data.pop("content", None)
            elif content:
                content_length = len(content)
                file_content = BytesIO(content.encode("utf-8"))
                file_data = {
                    "filename": f"N/A",
                    "content_type": "text/plain",
                }

                await self.providers.database.store_file(
                    id,
                    file_data["filename"],
                    file_content,
                    file_data["content_type"],
                )
            else:
                raise R2RException(
                    status_code=422,
                    message="Either a file or content must be provided.",
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
                raw_message: dict[str, Union[str, None]] = await self.orchestration_provider.run_workflow(  # type: ignore
                    "update-files", {"request": workflow_input}, {}
                )
                raw_message["message"] = "Update task queued successfully."
                raw_message["document_id"] = workflow_input["document_ids"][0]

                return raw_message  # type: ignore
            else:
                logger.info("Running update without orchestration.")
                # TODO - Clean up implementation logic here to be more explicitly `synchronous`
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(
                    self.services["ingestion"]
                )
                await simple_ingestor["update-files"](workflow_input)
                return {  # type: ignore
                    "message": "Update task completed successfully.",
                    "document_id": workflow_input["document_ids"],
                    "task_id": None,
                }

        @self.router.get("/documents")
        @self.base_endpoint
        async def get_documents(
            ids: list[str] = Query([]),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=-1),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[DocumentResponse]]:
            """
            Get a list of documents with pagination.
            """
            request_user_ids = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            filter_collection_ids = (
                None if auth_user.is_superuser else auth_user.collection_ids
            )

            document_uuids = [UUID(document_id) for document_id in ids]
            documents_overview_response = await self.services[
                "management"
            ].documents_overview(
                user_ids=request_user_ids,
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

        @self.router.get("/documents/{id}")
        @self.base_endpoint
        async def get_document(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[DocumentResponse]:
            """
            Get a specific document by its ID.
            """
            request_user_ids = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            filter_collection_ids = (
                None if auth_user.is_superuser else auth_user.collection_ids
            )

            documents_overview_response = await self.services[
                "management"
            ].documents_overview(
                user_ids=request_user_ids,
                collection_ids=filter_collection_ids,
                document_ids=[id],
            )
            results = documents_overview_response["results"]
            if len(results) == 0:
                raise R2RException("Document not found.", 404)

            return results[0]

        @self.router.get("/documents/{id}/chunks")
        @self.base_endpoint
        async def get_document_chunks(
            id: UUID = Path(...),
            offset: Optional[int] = Query(0, ge=0),
            limit: Optional[int] = Query(100, ge=0),
            include_vectors: Optional[bool] = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[ChunkResponse]]:
            """
            Get chunks for a specific document.
            """
            document_chunks = await self.services[
                "management"
            ].document_chunks(id, offset, limit, include_vectors)

            if not document_chunks["results"]:
                raise R2RException(
                    "No chunks found for the given document ID.", 404
                )

            is_owner = str(
                document_chunks["results"][0].get("user_id")
            ) == str(auth_user.id)
            document_collections = await self.services[
                "management"
            ].document_collections(id, 0, -1)

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
                document_chunks["results"],
                {"total_entries": document_chunks["total_entries"]},
            )

        @self.router.get(
            "/documents/{id}/download",
            response_class=StreamingResponse,
        )
        @self.base_endpoint
        async def get_document_file(
            id: str = Path(..., description="Document ID"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Download a file by its corresponding document ID.
            """
            # TODO: Add a check to see if the user has access to the file

            try:
                document_uuid = UUID(id)
            except ValueError:
                raise R2RException(
                    status_code=422, message="Invalid document ID format."
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

            return StreamingResponse(  # type: ignore
                file_stream(),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Content-Length": str(file_size),
                },
            )

        @self.router.delete("/documents/{id}")
        @self.base_endpoint
        async def delete_document_by_id(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[None]:
            """
            Delete a specific document.
            """
            filters = {
                "$and": [
                    {"$eq": str(auth_user.id)},
                    {"document_id": {"$eq": id}},
                ]
            }
            await self.services["management"].delete(filters=filters)
            return None

        @self.router.delete("/documents/by-filter")
        @self.base_endpoint
        async def delete_document_by_id(
            filters: str = Query(..., description="JSON-encoded filters"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[None]:
            """
            Delete documents based on provided filters.
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

            return await self.service.management.delete(filters=filters_dict)

        @self.router.get("/documents/{id}/collections")
        @self.base_endpoint
        async def get_document_collections(
            id: str = Path(..., description="Document ID"),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[list[CollectionResponse]]:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get the collections belonging to a document.",
                    403,
                )
            document_collections_response = await self.services[
                "management"
            ].document_collections(id, offset, limit)

            return document_collections_response["results"], {  # type: ignore
                "total_entries": document_collections_response["total_entries"]
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
