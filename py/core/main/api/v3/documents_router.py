import base64
import logging
import mimetypes
import textwrap
from datetime import datetime
from io import BytesIO
from typing import Any, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import Body, Depends, File, Form, Path, Query, UploadFile
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import Json

from core.base import (
    IngestionConfig,
    IngestionMode,
    R2RException,
    SearchMode,
    SearchSettings,
    UnprocessedChunk,
    Workflow,
    generate_document_id,
    generate_id,
    select_search_filters,
)
from core.base.abstractions import GraphCreationSettings, StoreType
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentSearchResponse,
    WrappedDocumentsResponse,
    WrappedEntitiesResponse,
    WrappedGenericMessageResponse,
    WrappedIngestionResponse,
    WrappedRelationshipsResponse,
)
from core.utils import update_settings_from_dict

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()
MAX_CHUNKS_PER_REQUEST = 1024 * 100


def merge_search_settings(
    base: SearchSettings, overrides: SearchSettings
) -> SearchSettings:
    # Convert both to dict
    base_dict = base.model_dump()
    overrides_dict = overrides.model_dump(exclude_unset=True)

    # Update base_dict with values from overrides_dict
    # This ensures that any field set in overrides takes precedence
    for k, v in overrides_dict.items():
        base_dict[k] = v

    # Construct a new SearchSettings from the merged dict
    return SearchSettings(**base_dict)


def merge_ingestion_config(
    base: IngestionConfig, overrides: IngestionConfig
) -> IngestionConfig:
    base_dict = base.model_dump()
    overrides_dict = overrides.model_dump(exclude_unset=True)

    for k, v in overrides_dict.items():
        base_dict[k] = v

    return IngestionConfig(**base_dict)


class DocumentsRouter(BaseRouterV3):
    def __init__(
        self,
        providers: R2RProviders,
        services: R2RServices,
        config: R2RConfig,
    ):
        logging.info("Initializing DocumentsRouter")
        super().__init__(providers, services, config)
        self._register_workflows()

    def _prepare_search_settings(
        self,
        auth_user: Any,
        search_mode: SearchMode,
        search_settings: Optional[SearchSettings],
    ) -> SearchSettings:
        """Prepare the effective search settings based on the provided
        search_mode, optional user-overrides in search_settings, and applied
        filters."""

        if search_mode != SearchMode.custom:
            # Start from mode defaults
            effective_settings = SearchSettings.get_default(search_mode.value)
            if search_settings:
                # Merge user-provided overrides
                effective_settings = merge_search_settings(
                    effective_settings, search_settings
                )
        else:
            # Custom mode: use provided settings or defaults
            effective_settings = search_settings or SearchSettings()

        # Apply user-specific filters
        effective_settings.filters = select_search_filters(
            auth_user, effective_settings
        )

        return effective_settings

    # TODO - Remove this legacy method
    def _register_workflows(self):
        self.providers.orchestration.register_workflows(
            Workflow.INGESTION,
            self.services.ingestion,
            {
                "ingest-files": (
                    "Ingest files task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Document created and ingested successfully."
                ),
                "ingest-chunks": (
                    "Ingest chunks task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Document created and ingested successfully."
                ),
                "update-chunk": (
                    "Update chunk task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Chunk update completed successfully."
                ),
                "update-document-metadata": (
                    "Update document metadata task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Document metadata update completed successfully."
                ),
                "create-vector-index": (
                    "Vector index creation task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Vector index creation task completed successfully."
                ),
                "delete-vector-index": (
                    "Vector index deletion task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Vector index deletion task completed successfully."
                ),
                "select-vector-index": (
                    "Vector index selection task queued successfully."
                    if self.providers.orchestration.config.provider != "simple"
                    else "Vector index selection task completed successfully."
                ),
            },
        )

    def _prepare_ingestion_config(
        self,
        ingestion_mode: IngestionMode,
        ingestion_config: Optional[IngestionConfig],
    ) -> IngestionConfig:
        # If not custom, start from defaults
        if ingestion_mode != IngestionMode.custom:
            effective_config = IngestionConfig.get_default(
                ingestion_mode.value, app=self.providers.auth.config.app
            )
            if ingestion_config:
                effective_config = merge_ingestion_config(
                    effective_config, ingestion_config
                )
        else:
            # custom mode
            effective_config = ingestion_config or IngestionConfig(
                app=self.providers.auth.config.app
            )

        effective_config.validate_config()
        return effective_config

    def _setup_routes(self):
        @self.router.post(
            "/documents",
            dependencies=[Depends(self.rate_limit_dependency)],
            status_code=202,
            summary="Create a new document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.create(
                                file_path="pg_essay_1.html",
                                metadata={"metadata_1":"some random metadata"},
                                id=None
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.create({
                                    file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
                                    metadata: { title: "marmeladov.txt" },
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/documents" \\
                            -H "Content-Type: multipart/form-data" \\
                            -H "Authorization: Bearer YOUR_API_KEY" \\
                            -F "file=@pg_essay_1.html;type=text/html" \\
                            -F 'metadata={}' \\
                            -F 'id=null'
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_document(
            file: Optional[UploadFile] = File(
                None,
                description="The file to ingest. Exactly one of file, raw_text, or chunks must be provided.",
            ),
            raw_text: Optional[str] = Form(
                None,
                description="Raw text content to ingest. Exactly one of file, raw_text, or chunks must be provided.",
            ),
            chunks: Optional[Json[list[str]]] = Form(
                None,
                description="Pre-processed text chunks to ingest. Exactly one of file, raw_text, or chunks must be provided.",
            ),
            id: Optional[UUID] = Form(
                None,
                description="The ID of the document. If not provided, a new ID will be generated.",
            ),
            collection_ids: Optional[Json[list[UUID]]] = Form(
                None,
                description="Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.",
            ),
            metadata: Optional[Json[dict]] = Form(
                None,
                description="Metadata to associate with the document, such as title, description, or custom fields.",
            ),
            ingestion_mode: IngestionMode = Form(
                default=IngestionMode.custom,
                description=(
                    "Ingestion modes:\n"
                    "- `hi-res`: Thorough ingestion with full summaries and enrichment.\n"
                    "- `fast`: Quick ingestion with minimal enrichment and no summaries.\n"
                    "- `custom`: Full control via `ingestion_config`.\n\n"
                    "If `filters` or `limit` (in `ingestion_config`) are provided alongside `hi-res` or `fast`, "
                    "they will override the default settings for that mode."
                ),
            ),
            ingestion_config: Optional[Json[IngestionConfig]] = Form(
                None,
                description="An optional dictionary to override the default chunking configuration for the ingestion process. If not provided, the system will use the default server-side chunking configuration.",
            ),
            run_with_orchestration: Optional[bool] = Form(
                True,
                description="Whether or not ingestion runs with orchestration, default is `True`. When set to `False`, the ingestion process will run synchronous and directly return the result.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedIngestionResponse:
            """
            Creates a new Document object from an input file, text content, or chunks. The chosen `ingestion_mode` determines
            how the ingestion process is configured:

            **Ingestion Modes:**
            - `hi-res`: Comprehensive parsing and enrichment, including summaries and possibly more thorough parsing.
            - `fast`: Speed-focused ingestion that skips certain enrichment steps like summaries.
            - `custom`: Provide a full `ingestion_config` to customize the entire ingestion process.

            Either a file or text content must be provided, but not both. Documents are shared through `Collections` which allow for tightly specified cross-user interactions.

            The ingestion process runs asynchronously and its progress can be tracked using the returned
            task_id.
            """
            if not auth_user.is_superuser:
                user_document_count = (
                    await self.services.management.documents_overview(
                        user_ids=[auth_user.id],
                        offset=0,
                        limit=1,
                    )
                )["total_entries"]
                user_max_documents = (
                    await self.services.management.get_user_max_documents(
                        auth_user.id
                    )
                )

                if user_document_count >= user_max_documents:
                    raise R2RException(
                        status_code=403,
                        message=f"User has reached the maximum number of documents allowed ({user_max_documents}).",
                    )

                # Get chunks using the vector handler's list_chunks method
                user_chunk_count = (
                    await self.services.ingestion.list_chunks(
                        filters={"owner_id": {"$eq": str(auth_user.id)}},
                        offset=0,
                        limit=1,
                    )
                )["total_entries"]
                user_max_chunks = (
                    await self.services.management.get_user_max_chunks(
                        auth_user.id
                    )
                )
                if user_chunk_count >= user_max_chunks:
                    raise R2RException(
                        status_code=403,
                        message=f"User has reached the maximum number of chunks allowed ({user_max_chunks}).",
                    )

                user_collections_count = (
                    await self.services.management.collections_overview(
                        user_ids=[auth_user.id],
                        offset=0,
                        limit=1,
                    )
                )["total_entries"]
                user_max_collections = (
                    await self.services.management.get_user_max_collections(
                        auth_user.id
                    )
                )
                if user_collections_count >= user_max_collections:  # type: ignore
                    raise R2RException(
                        status_code=403,
                        message=f"User has reached the maximum number of collections allowed ({user_max_collections}).",
                    )

            effective_ingestion_config = self._prepare_ingestion_config(
                ingestion_mode=ingestion_mode,
                ingestion_config=ingestion_config,
            )
            if not file and not raw_text and not chunks:
                raise R2RException(
                    status_code=422,
                    message="Either a `file`, `raw_text`, or `chunks` must be provided.",
                )
            if (
                (file and raw_text)
                or (file and chunks)
                or (raw_text and chunks)
            ):
                raise R2RException(
                    status_code=422,
                    message="Only one of `file`, `raw_text`, or `chunks` may be provided.",
                )
            # Check if the user is a superuser
            metadata = metadata or {}

            if chunks:
                if len(chunks) == 0:
                    raise R2RException("Empty list of chunks provided", 400)

                if len(chunks) > MAX_CHUNKS_PER_REQUEST:
                    raise R2RException(
                        f"Maximum of {MAX_CHUNKS_PER_REQUEST} chunks per request",
                        400,
                    )

                document_id = id or generate_document_id(
                    "".join(chunks), auth_user.id
                )

                # FIXME: Metadata doesn't seem to be getting passed through
                raw_chunks_for_doc = [
                    UnprocessedChunk(
                        text=chunk,
                        metadata=metadata,
                        id=generate_id(),
                    )
                    for chunk in chunks
                ]

                # Prepare workflow input
                workflow_input = {
                    "document_id": str(document_id),
                    "chunks": [
                        chunk.model_dump(mode="json")
                        for chunk in raw_chunks_for_doc
                    ],
                    "metadata": metadata,  # Base metadata for the document
                    "user": auth_user.model_dump_json(),
                    "ingestion_config": effective_ingestion_config.model_dump(
                        mode="json"
                    ),
                }

                if run_with_orchestration:
                    try:
                        # Run ingestion with orchestration
                        raw_message = (
                            await self.providers.orchestration.run_workflow(
                                "ingest-chunks",
                                {"request": workflow_input},
                                options={
                                    "additional_metadata": {
                                        "document_id": str(document_id),
                                    }
                                },
                            )
                        )
                        raw_message["document_id"] = str(document_id)
                        return raw_message  # type: ignore
                    except Exception as e:  # TODO: Need to find specific errors that we should be excepting (gRPC most likely?)
                        logger.error(
                            f"Error running orchestrated ingestion: {e} \n\nAttempting to run without orchestration."
                        )

                logger.info("Running chunk ingestion without orchestration.")
                from core.main.orchestration import simple_ingestion_factory

                simple_ingestor = simple_ingestion_factory(
                    self.services.ingestion
                )
                await simple_ingestor["ingest-chunks"](workflow_input)

                return {  # type: ignore
                    "message": "Document created and ingested successfully.",
                    "document_id": str(document_id),
                    "task_id": None,
                }

            else:
                if file:
                    file_data = await self._process_file(file)

                    if not file.filename:
                        raise R2RException(
                            status_code=422,
                            message="Uploaded file must have a filename.",
                        )

                    file_ext = file.filename.split(".")[
                        -1
                    ]  # e.g. "pdf", "txt"
                    max_allowed_size = await self.services.management.get_max_upload_size_by_type(
                        user_id=auth_user.id, file_type_or_ext=file_ext
                    )

                    content_length = file_data["content_length"]

                    if content_length > max_allowed_size:
                        raise R2RException(
                            status_code=413,  # HTTP 413: Payload Too Large
                            message=(
                                f"File size exceeds maximum of {max_allowed_size} bytes "
                                f"for extension '{file_ext}'."
                            ),
                        )

                    file_content = BytesIO(
                        base64.b64decode(file_data["content"])
                    )

                    file_data.pop("content", None)
                    document_id = id or generate_document_id(
                        file_data["filename"], auth_user.id
                    )
                elif raw_text:
                    content_length = len(raw_text)
                    file_content = BytesIO(raw_text.encode("utf-8"))
                    document_id = id or generate_document_id(
                        raw_text, auth_user.id
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
                "collection_ids": (
                    [str(cid) for cid in collection_ids]
                    if collection_ids
                    else None
                ),
                "metadata": metadata,
                "ingestion_config": effective_ingestion_config.model_dump(
                    mode="json"
                ),
                "user": auth_user.model_dump_json(),
                "size_in_bytes": content_length,
                "version": "v0",
            }

            file_name = file_data["filename"]
            await self.providers.database.files_handler.store_file(
                document_id,
                file_name,
                file_content,
                file_data["content_type"],
            )

            await self.services.ingestion.ingest_file_ingress(
                file_data=workflow_input["file_data"],
                user=auth_user,
                document_id=workflow_input["document_id"],
                size_in_bytes=workflow_input["size_in_bytes"],
                metadata=workflow_input["metadata"],
                version=workflow_input["version"],
            )

            if run_with_orchestration:
                try:
                    # TODO - Modify create_chunks so that we can add chunks to existing document

                    workflow_result: dict[
                        str, str | None
                    ] = await self.providers.orchestration.run_workflow(  # type: ignore
                        "ingest-files",
                        {"request": workflow_input},
                        options={
                            "additional_metadata": {
                                "document_id": str(document_id),
                            }
                        },
                    )
                    workflow_result["document_id"] = str(document_id)
                    return workflow_result  # type: ignore
                except Exception as e:  # TODO: Need to find specific error (gRPC most likely?)
                    logger.error(
                        f"Error running orchestrated ingestion: {e} \n\nAttempting to run without orchestration."
                    )
            logger.info(
                f"Running ingestion without orchestration for file {file_name} and document_id {document_id}."
            )
            # TODO - Clean up implementation logic here to be more explicitly `synchronous`
            from core.main.orchestration import simple_ingestion_factory

            simple_ingestor = simple_ingestion_factory(self.services.ingestion)
            await simple_ingestor["ingest-files"](workflow_input)
            return {  # type: ignore
                "message": "Document created and ingested successfully.",
                "document_id": str(document_id),
                "task_id": None,
            }

        @self.router.post(
            "/documents/export",
            summary="Export documents to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.documents.export(
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.documents.export({
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/documents/export" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_documents(
            background_tasks: BackgroundTasks,
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_documents(
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="documents_export.csv",
            )

        @self.router.get(
            "/documents/download_zip",
            dependencies=[Depends(self.rate_limit_dependency)],
            response_class=StreamingResponse,
            summary="Export multiple documents as zip",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            client.documents.download_zip(
                                document_ids=["uuid1", "uuid2"],
                                start_date="2024-01-01",
                                end_date="2024-12-31"
                            )
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/download_zip?document_ids=uuid1,uuid2&start_date=2024-01-01&end_date=2024-12-31" \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_files(
            document_ids: Optional[list[UUID]] = Query(
                None,
                description="List of document IDs to include in the export. If not provided, all accessible documents will be included.",
            ),
            start_date: Optional[datetime] = Query(
                None,
                description="Filter documents created on or after this date.",
            ),
            end_date: Optional[datetime] = Query(
                None,
                description="Filter documents created before this date.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> StreamingResponse:
            """Export multiple documents as a zip file. Documents can be
            filtered by IDs and/or date range.

            The endpoint allows downloading:
            - Specific documents by providing their IDs
            - Documents within a date range
            - All accessible documents if no filters are provided

            Files are streamed as a zip archive to handle potentially large downloads efficiently.
            """
            if not auth_user.is_superuser:
                # For non-superusers, verify access to requested documents
                if document_ids:
                    documents_overview = (
                        await self.services.management.documents_overview(
                            user_ids=[auth_user.id],
                            document_ids=document_ids,
                            offset=0,
                            limit=len(document_ids),
                        )
                    )
                    if len(documents_overview["results"]) != len(document_ids):
                        raise R2RException(
                            status_code=403,
                            message="You don't have access to one or more requested documents.",
                        )
                if not document_ids:
                    raise R2RException(
                        status_code=403,
                        message="Non-superusers must provide document IDs to export.",
                    )

            (
                zip_name,
                zip_content,
                zip_size,
            ) = await self.services.management.export_files(
                document_ids=document_ids,
                start_date=start_date,
                end_date=end_date,
            )
            encoded_filename = quote(zip_name)

            async def stream_file():
                yield zip_content.getvalue()

            return StreamingResponse(
                stream_file(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                    "Content-Length": str(zip_size),
                },
            )

        @self.router.get(
            "/documents",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List documents",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.list(
                                limit=10,
                                offset=0
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.list({
                                    limit: 10,
                                    offset: 0,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            include_summary_embeddings: bool = Query(
                False,
                description="Specifies whether or not to include embeddings of each document summary.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedDocumentsResponse:
            """Returns a paginated list of documents the authenticated user has
            access to.

            Results can be filtered by providing specific document IDs. Regular
            users will only see documents they own or have access to through
            collections. Superusers can see all documents.

            The documents are returned in order of last modification, with most
            recent first.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            filter_collection_ids = (
                None if auth_user.is_superuser else auth_user.collection_ids
            )

            document_uuids = [UUID(document_id) for document_id in ids]
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=requesting_user_id,
                    collection_ids=filter_collection_ids,
                    document_ids=document_uuids,
                    offset=offset,
                    limit=limit,
                )
            )
            if not include_summary_embeddings:
                for document in documents_overview_response["results"]:
                    document.summary_embedding = None

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
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Retrieve a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.retrieve(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.retrieve({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedDocumentResponse:
            """Retrieves detailed information about a specific document by its
            ID.

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

            documents_overview_response = await self.services.management.documents_overview(  # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
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
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List document chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.list_chunks(
                                id="32b6a70f-a995-5c51-85d2-834f06283a1e"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.listChunks({
                                    id: "32b6a70f-a995-5c51-85d2-834f06283a1e",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/chunks"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"\
                            """),
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
            include_vectors: Optional[bool] = Query(
                False,
                description="Whether to include vector embeddings in the response.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedChunksResponse:
            """Retrieves the text chunks that were generated from a document
            during ingestion. Chunks represent semantic sections of the
            document and are used for retrieval and analysis.

            Users can only access chunks from documents they own or have access
            to through collections. Vector embeddings are only included if
            specifically requested.

            Results are returned in chunk sequence order, representing their
            position in the original document.
            """
            list_document_chunks = (
                await self.services.management.list_document_chunks(
                    document_id=id,
                    offset=offset,
                    limit=limit,
                    include_vectors=include_vectors or False,
                )
            )

            if not list_document_chunks["results"]:
                raise R2RException(
                    "No chunks found for the given document ID.", 404
                )

            is_owner = str(
                list_document_chunks["results"][0].get("owner_id")
            ) == str(auth_user.id)
            document_collections = (
                await self.services.management.collections_overview(
                    offset=0,
                    limit=-1,
                    document_ids=[id],
                )
            )

            user_has_access = (
                is_owner
                or set(auth_user.collection_ids).intersection(
                    {ele.id for ele in document_collections["results"]}  # type: ignore
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
            dependencies=[Depends(self.rate_limit_dependency)],
            response_class=StreamingResponse,
            summary="Download document content",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.download(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.download({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/download"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_document_file(
            id: str = Path(..., description="Document ID"),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> StreamingResponse:
            """Downloads the original file content of a document.

            For uploaded files, returns the original file with its proper MIME
            type. For text-only documents, returns the content as plain text.

            Users can only download documents they own or have access to
            through collections.
            """
            try:
                document_uuid = UUID(id)
            except ValueError:
                raise R2RException(
                    status_code=422, message="Invalid document ID format."
                ) from None

            # Retrieve the document's information
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=None,
                    collection_ids=None,
                    document_ids=[document_uuid],
                    offset=0,
                    limit=1,
                )
            )

            if not documents_overview_response["results"]:
                raise R2RException("Document not found.", 404)

            document = documents_overview_response["results"][0]

            is_owner = str(document.owner_id) == str(auth_user.id)

            if not auth_user.is_superuser and not is_owner:
                document_collections = (
                    await self.services.management.collections_overview(
                        offset=0,
                        limit=-1,
                        document_ids=[document_uuid],
                    )
                )

                document_collection_ids = {
                    str(ele.id)
                    for ele in document_collections["results"]  # type: ignore
                }

                user_collection_ids = {
                    str(cid) for cid in auth_user.collection_ids
                }

                has_collection_access = user_collection_ids.intersection(
                    document_collection_ids
                )

                if not has_collection_access:
                    raise R2RException(
                        "Not authorized to access this document.", 403
                    )

            file_tuple = await self.services.management.download_file(
                document_uuid
            )
            if not file_tuple:
                raise R2RException(status_code=404, message="File not found.")

            file_name, file_content, file_size = file_tuple
            encoded_filename = quote(file_name)

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
                    "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}",
                    "Content-Length": str(file_size),
                },
            )

        @self.router.delete(
            "/documents/by-filter",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete documents by filter",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient
                            client = R2RClient()
                            # when using auth, do client.login(...)
                            response = client.documents.delete_by_filter(
                                filters={"document_type": {"$eq": "txt"}}
                            )
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/documents/by-filter?filters=%7B%22document_type%22%3A%7B%22%24eq%22%3A%22text%22%7D%2C%22created_at%22%3A%7B%22%24lt%22%3A%222023-01-01T00%3A00%3A00Z%22%7D%7D" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_document_by_filter(
            filters: Json[dict] = Body(
                ..., description="JSON-encoded filters"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete documents based on provided filters.

            Allowed operators
            include: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`,
            `ilike`, `in`, and `nin`. Deletion requests are limited to a
            user's own documents.
            """

            filters_dict = {
                "$and": [{"owner_id": {"$eq": str(auth_user.id)}}, filters]
            }
            await (
                self.services.management.delete_documents_and_chunks_by_filter(
                    filters=filters_dict
                )
            )

            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.delete(
            "/documents/{id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.delete(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.delete({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa" \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_document_by_id(
            id: UUID = Path(..., description="Document ID"),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete a specific document. All chunks corresponding to the
            document are deleted, and all other references to the document are
            removed.

            NOTE - Deletions do not yet impact the knowledge graph or other derived data. This feature is planned for a future release.
            """

            filters: dict[str, Any] = {"document_id": {"$eq": str(id)}}
            if not auth_user.is_superuser:
                filters = {
                    "$and": [
                        {"owner_id": {"$eq": str(auth_user.id)}},
                        {"document_id": {"$eq": str(id)}},
                    ]
                }

            await (
                self.services.management.delete_documents_and_chunks_by_filter(
                    filters=filters
                )
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/documents/{id}/collections",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List document collections",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.list_collections(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa", offset=0, limit=10
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.listCollections({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/collections"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionsResponse:
            """Retrieves all collections that contain the specified document.
            This endpoint is restricted to superusers only and provides a
            system-wide view of document organization.

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

            collections_response = (
                await self.services.management.collections_overview(
                    offset=offset,
                    limit=limit,
                    document_ids=[UUID(id)],  # Convert string ID to UUID
                )
            )

            return collections_response["results"], {  # type: ignore
                "total_entries": collections_response["total_entries"]
            }

        @self.router.post(
            "/documents/{id}/extract",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Extract entities and relationships",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.extract(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def extract(
            id: UUID = Path(
                ...,
                description="The ID of the document to extract entities and relationships from.",
            ),
            settings: Optional[GraphCreationSettings] = Body(
                default=None,
                description="Settings for the entities and relationships extraction process.",
            ),
            run_with_orchestration: Optional[bool] = Body(
                default=True,
                description="Whether to run the entities and relationships extraction process with orchestration.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Extracts entities and relationships from a document.

            The entities and relationships extraction process involves:

                1. Parsing documents into semantic chunks

                2. Extracting entities and relationships using LLMs

                3. Storing the created entities and relationships in the knowledge graph

                4. Preserving the document's metadata and content, and associating the elements with collections the document belongs to
            """

            settings = settings.dict() if settings else None  # type: ignore
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=(
                        None if auth_user.is_superuser else [auth_user.id]
                    ),
                    collection_ids=(
                        None
                        if auth_user.is_superuser
                        else auth_user.collection_ids
                    ),
                    document_ids=[id],
                    offset=0,
                    limit=1,
                )
            )["results"]
            if len(documents_overview_response) == 0:
                raise R2RException("Document not found.", 404)

            if (
                not auth_user.is_superuser
                and auth_user.id != documents_overview_response[0].owner_id
            ):
                raise R2RException(
                    "Only a superuser can extract entities and relationships from a document they do not own.",
                    403,
                )

            # Apply runtime settings overrides
            server_graph_creation_settings = (
                self.providers.database.config.graph_creation_settings
            )

            if settings:
                server_graph_creation_settings = update_settings_from_dict(
                    server_settings=server_graph_creation_settings,
                    settings_dict=settings,  # type: ignore
                )

            if run_with_orchestration:
                try:
                    workflow_input = {
                        "document_id": str(id),
                        "graph_creation_settings": server_graph_creation_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.providers.orchestration.run_workflow(  # type: ignore
                        "graph-extraction", {"request": workflow_input}, {}
                    )
                except Exception as e:  # TODO: Need to find specific errors that we should be excepting (gRPC most likely?)
                    logger.error(
                        f"Error running orchestrated extraction: {e} \n\nAttempting to run without orchestration."
                    )

            from core.main.orchestration import (
                simple_graph_search_results_factory,
            )

            logger.info("Running extract-triples without orchestration.")
            simple_graph_search_results = simple_graph_search_results_factory(
                self.services.graph
            )
            await simple_graph_search_results["graph-extraction"](
                workflow_input
            )
            return {  # type: ignore
                "message": "Graph created successfully.",
                "task_id": None,
            }

        @self.router.post(
            "/documents/{id}/deduplicate",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Deduplicate entities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()

                            response = client.documents.deduplicate(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.deduplicate({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/deduplicate"  \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def deduplicate(
            id: UUID = Path(
                ...,
                description="The ID of the document to extract entities and relationships from.",
            ),
            settings: Optional[GraphCreationSettings] = Body(
                default=None,
                description="Settings for the entities and relationships extraction process.",
            ),
            run_with_orchestration: Optional[bool] = Body(
                default=True,
                description="Whether to run the entities and relationships extraction process with orchestration.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Deduplicates entities from a document."""

            settings = settings.model_dump() if settings else None  # type: ignore
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=(
                        None if auth_user.is_superuser else [auth_user.id]
                    ),
                    collection_ids=(
                        None
                        if auth_user.is_superuser
                        else auth_user.collection_ids
                    ),
                    document_ids=[id],
                    offset=0,
                    limit=1,
                )
            )["results"]
            if len(documents_overview_response) == 0:
                raise R2RException("Document not found.", 404)

            if (
                not auth_user.is_superuser
                and auth_user.id != documents_overview_response[0].owner_id
            ):
                raise R2RException(
                    "Only a superuser can run deduplication on a document they do not own.",
                    403,
                )

            # Apply runtime settings overrides
            server_graph_creation_settings = (
                self.providers.database.config.graph_creation_settings
            )

            if settings:
                server_graph_creation_settings = update_settings_from_dict(
                    server_settings=server_graph_creation_settings,
                    settings_dict=settings,  # type: ignore
                )

            if run_with_orchestration:
                try:
                    workflow_input = {
                        "document_id": str(id),
                    }

                    return await self.providers.orchestration.run_workflow(  # type: ignore
                        "graph-deduplication",
                        {"request": workflow_input},
                        {},
                    )
                except Exception as e:  # TODO: Need to find specific errors that we should be excepting (gRPC most likely?)
                    logger.error(
                        f"Error running orchestrated deduplication: {e} \n\nAttempting to run without orchestration."
                    )

            from core.main.orchestration import (
                simple_graph_search_results_factory,
            )

            logger.info(
                "Running deduplicate-document-entities without orchestration."
            )
            simple_graph_search_results = simple_graph_search_results_factory(
                self.services.graph
            )
            await simple_graph_search_results["graph-deduplication"](
                workflow_input
            )
            return {  # type: ignore
                "message": "Graph created successfully.",
                "task_id": None,
            }

        @self.router.get(
            "/documents/{id}/entities",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Lists the entities from the document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.extract(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def get_entities(
            id: UUID = Path(
                ...,
                description="The ID of the document to retrieve entities from.",
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
            include_embeddings: Optional[bool] = Query(
                False,
                description="Whether to include vector embeddings in the response.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedEntitiesResponse:
            """Retrieves the entities that were extracted from a document.
            These represent important semantic elements like people, places,
            organizations, concepts, etc.

            Users can only access entities from documents they own or have
            access to through collections. Entity embeddings are only included
            if specifically requested.

            Results are returned in the order they were extracted from the
            document.
            """
            # if (
            #     not auth_user.is_superuser
            #     and id not in auth_user.collection_ids
            # ):
            #     raise R2RException(
            #         "The currently authenticated user does not have access to the specified collection.",
            #         403,
            #     )

            # First check if the document exists and user has access
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=(
                        None if auth_user.is_superuser else [auth_user.id]
                    ),
                    collection_ids=(
                        None
                        if auth_user.is_superuser
                        else auth_user.collection_ids
                    ),
                    document_ids=[id],
                    offset=0,
                    limit=1,
                )
            )

            if not documents_overview_response["results"]:
                raise R2RException("Document not found.", 404)

            # Get all entities for this document from the document_entity table
            (
                entities,
                count,
            ) = await self.providers.database.graphs_handler.entities.get(
                parent_id=id,
                store_type=StoreType.DOCUMENTS,
                offset=offset,
                limit=limit,
                include_embeddings=include_embeddings or False,
            )

            return entities, {"total_entries": count}  # type: ignore

        @self.router.post(
            "/documents/{id}/entities/export",
            summary="Export document entities to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.documents.export_entities(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.documents.exportEntities({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/documents/export_entities" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_entities(
            background_tasks: BackgroundTasks,
            id: UUID = Path(
                ...,
                description="The ID of the document to export entities from.",
            ),
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_document_entities(
                id=id,
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="documents_export.csv",
            )

        @self.router.get(
            "/documents/{id}/relationships",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List document relationships",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.documents.list_relationships(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                offset=0,
                                limit=100
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.documents.listRelationships({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    offset: 0,
                                    limit: 100,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/documents/b4ac4dd6-5f27-596e-a55b-7cf242ca30aa/relationships" \\
                            -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_relationships(
            id: UUID = Path(
                ...,
                description="The ID of the document to retrieve relationships for.",
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
            entity_names: Optional[list[str]] = Query(
                None,
                description="Filter relationships by specific entity names.",
            ),
            relationship_types: Optional[list[str]] = Query(
                None,
                description="Filter relationships by specific relationship types.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedRelationshipsResponse:
            """Retrieves the relationships between entities that were extracted
            from a document. These represent connections and interactions
            between entities found in the text.

            Users can only access relationships from documents they own or have
            access to through collections. Results can be filtered by entity
            names and relationship types.

            Results are returned in the order they were extracted from the
            document.
            """
            # if (
            #     not auth_user.is_superuser
            #     and id not in auth_user.collection_ids
            # ):
            #     raise R2RException(
            #         "The currently authenticated user does not have access to the specified collection.",
            #         403,
            #     )

            # First check if the document exists and user has access
            documents_overview_response = (
                await self.services.management.documents_overview(
                    user_ids=(
                        None if auth_user.is_superuser else [auth_user.id]
                    ),
                    collection_ids=(
                        None
                        if auth_user.is_superuser
                        else auth_user.collection_ids
                    ),
                    document_ids=[id],
                    offset=0,
                    limit=1,
                )
            )

            if not documents_overview_response["results"]:
                raise R2RException("Document not found.", 404)

            # Get relationships for this document
            (
                relationships,
                count,
            ) = await self.providers.database.graphs_handler.relationships.get(
                parent_id=id,
                store_type=StoreType.DOCUMENTS,
                entity_names=entity_names,
                relationship_types=relationship_types,
                offset=offset,
                limit=limit,
            )

            return relationships, {"total_entries": count}  # type: ignore

        @self.router.post(
            "/documents/{id}/relationships/export",
            summary="Export document relationships to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.documents.export_entities(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.documents.exportEntities({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/documents/export_entities" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_relationships(
            background_tasks: BackgroundTasks,
            id: UUID = Path(
                ...,
                description="The ID of the document to export entities from.",
            ),
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_document_relationships(
                id=id,
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="documents_export.csv",
            )

        @self.router.post(
            "/documents/search",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Search document summaries",
        )
        @self.base_endpoint
        async def search_documents(
            query: str = Body(
                ...,
                description="The search query to perform.",
            ),
            search_mode: SearchMode = Body(
                default=SearchMode.custom,
                description=(
                    "Default value of `custom` allows full control over search settings.\n\n"
                    "Pre-configured search modes:\n"
                    "`basic`: A simple semantic-based search.\n"
                    "`advanced`: A more powerful hybrid search combining semantic and full-text.\n"
                    "`custom`: Full control via `search_settings`.\n\n"
                    "If `filters` or `limit` are provided alongside `basic` or `advanced`, "
                    "they will override the default settings for that mode."
                ),
            ),
            search_settings: SearchSettings = Body(
                default_factory=SearchSettings,
                description="Settings for document search",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedDocumentSearchResponse:
            """Perform a search query on the automatically generated document
            summaries in the system.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.


            Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.
            """
            effective_settings = self._prepare_search_settings(
                auth_user, search_mode, search_settings
            )

            query_embedding = (
                await self.providers.embedding.async_get_embedding(query)
            )
            results = await self.services.retrieval.search_documents(
                query=query,
                query_embedding=query_embedding,
                settings=effective_settings,
            )
            return results  # type: ignore

    @staticmethod
    async def _process_file(file):
        import base64

        content = await file.read()

        return {
            "filename": file.filename,
            "content": base64.b64encode(content).decode("utf-8"),
            "content_type": file.content_type,
            "content_length": len(content),
        }
