import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import UploadFile

from core.base import (
    Document,
    DocumentInfo,
    DocumentType,
    R2RDocumentProcessingError,
    R2RException,
    RunLoggingSingleton,
    RunManager,
    generate_user_document_id,
    increment_version,
    to_async_generator,
)
from core.base.api.models import IngestionResponse
from core.base.providers import ChunkingProvider
from core.telemetry.telemetry_decorator import telemetry_event

from ...base.api.models.auth.responses import UserResponse
from ..abstractions import R2RAgents, R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)
MB_CONVERSION_FACTOR = 1024 * 1024
STARTING_VERSION = "v0"
MAX_FILES_PER_INGESTION = 100
OVERVIEW_FETCH_PAGE_SIZE = 1_000


class IngestionService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("IngestFiles")
    async def ingest_files(
        self,
        files: list[UploadFile],
        user: UserResponse,
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[UUID]] = None,
        chunking_provider: Optional[ChunkingProvider] = None,
        *args: Any,
        **kwargs: Any,
    ) -> IngestionResponse:
        if not files:
            raise R2RException(
                status_code=400, message="No files provided for ingestion."
            )
        if len(files) > MAX_FILES_PER_INGESTION:
            raise R2RException(
                status_code=400,
                message=f"Exceeded maximum number of files per ingestion: {MAX_FILES_PER_INGESTION}.",
            )
        try:
            documents = []
            for iteration, file in enumerate(files):
                if not file.filename:
                    raise R2RException(
                        status_code=400, message="File name not provided."
                    )

                document_metadata = metadatas[iteration] if metadatas else {}

                # document id is dynamically generated from the filename and user id, unless explicitly provided
                document_id = (
                    document_ids[iteration]
                    if document_ids
                    else generate_user_document_id(file.filename, user.id)
                )
                document = self._file_to_document(
                    file, user, document_id, document_metadata
                )
                documents.append(document)
            # ingests all documents in parallel
            return await self.ingest_documents(
                documents,
                chunking_provider=chunking_provider,
                *args,
                **kwargs,
            )

        finally:
            for file in files:
                file.file.close()

    @telemetry_event("UpdateFiles")
    async def update_files(
        self,
        files: list[UploadFile],
        user: UserResponse,
        document_ids: Optional[list[UUID]],
        metadatas: Optional[list[dict]] = None,
        chunking_provider: Optional[ChunkingProvider] = None,
        *args: Any,
        **kwargs: Any,
    ) -> IngestionResponse:
        if not files:
            raise R2RException(
                status_code=400, message="No files provided for update."
            )
        if not self.providers.database:
            raise R2RException(
                status_code=501,
                message="Database provider is not available for updating documents.",
            )
        try:
            if document_ids:
                if len(document_ids) != len(files):
                    raise R2RException(
                        status_code=400,
                        message="Number of ids does not match number of files.",
                    )
            else:
                document_ids = [
                    generate_user_document_id(file.filename, user.id)
                    for file in files
                ]
            if len(files) > MAX_FILES_PER_INGESTION:
                raise R2RException(
                    status_code=400,
                    message=f"Exceeded maximum number of files per ingestion: {MAX_FILES_PER_INGESTION}.",
                )

            documents_overview = []

            offset = 0
            while True:
                documents_overview_page = (
                    self.providers.database.relational.get_documents_overview(
                        filter_document_ids=document_ids,
                        filter_user_ids=(
                            [user.id] if not user.is_superuser else None
                        ),
                        offset=offset,
                        limit=OVERVIEW_FETCH_PAGE_SIZE,
                    )
                )
                documents_overview.extend(documents_overview_page)
                if len(documents_overview_page) < OVERVIEW_FETCH_PAGE_SIZE:
                    break
                offset += 1

            documents = []
            new_versions = []

            for it, (file, doc_id, doc_info) in enumerate(
                zip(files, document_ids, documents_overview)
            ):
                if not doc_info:
                    raise R2RException(
                        status_code=404,
                        message=f"Document with id {doc_id} not found.",
                    )

                new_version = increment_version(doc_info.version)
                new_versions.append(new_version)

                updated_metadata = (
                    metadatas[it] if metadatas else doc_info.metadata
                )
                updated_metadata["title"] = (
                    updated_metadata.get("title", None)
                    or file.filename.split("/")[-1]
                )

                document = self._file_to_document(
                    file, user, doc_id, updated_metadata
                )
                documents.append(document)

            ingestion_results = await self.ingest_documents(
                documents,
                chunking_provider=chunking_provider,
                versions=new_versions,
                *args,
                **kwargs,
            )

            for doc_id, old_version in zip(
                document_ids,
                [doc_info.version for doc_info in documents_overview],
            ):
                self.providers.database.vector.delete(
                    filters={
                        "document_id": {"$eq": doc_id},
                        "version": {"$eq": old_version},
                    }
                )
                self.providers.database.relational.delete_from_documents_overview(
                    doc_id, old_version
                )

            return ingestion_results

        finally:
            for file in files:
                file.file.close()

    async def ingest_documents(
        self,
        documents: list[Document],
        versions: Optional[list[str]] = None,
        chunking_provider: Optional[ChunkingProvider] = None,
        *args: Any,
        **kwargs: Any,
    ):

        if len(documents) == 0:
            raise R2RException(
                status_code=400, message="No documents provided for ingestion."
            )

        if chunking_provider is None:
            logger.info("No chunking provider specified. Using default.")
        else:
            logger.info(
                f"Using custom chunking provider: {type(chunking_provider).__name__}"
            )

        document_infos = []
        skipped_documents = []
        processed_documents = {}
        duplicate_documents = defaultdict(list)

        if not all(doc.id for doc in documents):
            raise R2RException(
                status_code=400, message="All documents must have an ID."
            )
        user_id = documents[0].user_id

        existing_documents = (
            (
                self.providers.database.relational.get_documents_overview(
                    filter_user_ids=[user_id]
                )
            )
            if self.providers.database
            else []
        )

        existing_document_info = {
            doc_info.id: doc_info for doc_info in existing_documents
        }

        for iteration, document in enumerate(documents):
            version = versions[iteration] if versions else STARTING_VERSION

            # Check for duplicates within the current batch
            if document.id in processed_documents:
                duplicate_documents[document.id].append(
                    document.metadata.get("title", str(document.id))
                )
                continue

            if (
                document.id in existing_document_info
                # apply `geq` check to prevent re-ingestion of updated documents
                and (existing_document_info[document.id].version >= version)
                and existing_document_info[document.id].ingestion_status
                == "success"
            ):
                logger.error(
                    f"Document with ID {document.id} was already successfully processed."
                )
                if len(documents) == 1:
                    raise R2RException(
                        status_code=409,
                        message=f"Document with ID {document.id} was already successfully processed.",
                    )
                skipped_documents.append(
                    {
                        "id": document.id,
                        "title": document.metadata.get("title", "N/A"),
                    }
                )
                continue

            now = datetime.now()
            document_info_metadata = document.metadata.copy()
            title = document_info_metadata.pop("title", "N/A")

            document_infos.append(
                DocumentInfo(
                    id=document.id,
                    user_id=document.user_id,
                    group_ids=document.group_ids,
                    type=document.type,
                    metadata=document_info_metadata,
                    title=title,
                    version=version,
                    size_in_bytes=len(document.data),
                    ingestion_status="processing",
                    created_at=now,
                    updated_at=now,
                )
            )

            processed_documents[document.id] = document.metadata.get(
                "title", str(document.id)
            )
            # Add version to metadata to propagate through pipeline
            document.metadata["version"] = version

        if duplicate_documents:
            duplicate_details = [
                f"{doc_id}: {', '.join(titles)}"
                for doc_id, titles in duplicate_documents.items()
            ]
            warning_message = f"Duplicate documents detected: {'; '.join(duplicate_details)}. These duplicates were skipped."
            raise R2RException(status_code=418, message=warning_message)

        if skipped_documents and len(skipped_documents) == len(documents):
            logger.error("All provided documents already exist.")
            raise R2RException(
                status_code=409,
                message="All provided documents already exist. Use the `update_files` endpoint instead to update these documents.",
            )

        # Insert pending document info
        if self.providers.database:
            self.providers.database.relational.upsert_documents_overview(
                document_infos
            )

        ingestion_results = await self.pipelines.ingestion_pipeline.run(
            input=to_async_generator(
                [
                    doc
                    for doc in documents
                    if doc.id
                    not in [skipped["id"] for skipped in skipped_documents]
                ],
            ),
            run_manager=self.run_manager,
            *args,
            **kwargs,
        )

        return await self._process_ingestion_results(
            ingestion_results,
            document_infos,
            skipped_documents,
        )

    def _file_to_document(
        self,
        file: UploadFile,
        user: UserResponse,
        document_id: UUID,
        metadata: dict,
    ) -> Document:
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension.upper() not in DocumentType.__members__:
            raise R2RException(
                status_code=415,
                message=f"'{file_extension}' is not a valid DocumentType.",
            )

        document_title = metadata.get("title") or file.filename.split("/")[-1]
        metadata["title"] = document_title

        return Document(
            id=document_id,
            group_ids=metadata.get("group_ids", []),
            user_id=user.id,
            type=DocumentType[file_extension.upper()],
            data=file.file.read(),
            metadata=metadata,
        )

    async def _process_ingestion_results(
        self,
        ingestion_results: dict,
        document_infos: list[DocumentInfo],
        skipped_documents: list[dict[str, str]],
    ):
        skipped_ids = [ele["id"] for ele in skipped_documents]
        failed_ids = []
        successful_ids = []

        results = {}
        if ingestion_results["embedding_pipeline_output"]:
            results = dict(ingestion_results["embedding_pipeline_output"])
            for doc_id, error in results.items():
                if isinstance(error, R2RDocumentProcessingError):
                    logger.error(
                        f"Error processing document with ID {error.document_id}: {error.message}"
                    )
                    failed_ids.append(error.document_id)
                elif isinstance(error, Exception):
                    logger.error(f"Error processing document: {error}")
                    failed_ids.append(doc_id)
                else:
                    successful_ids.append(doc_id)

        documents_to_upsert = []
        for document_info in document_infos:
            if document_info.id not in skipped_ids:
                if document_info.id in failed_ids:
                    document_info.ingestion_status = "failure"
                elif document_info.id in successful_ids:
                    document_info.ingestion_status = "success"
                documents_to_upsert.append(document_info)

        if documents_to_upsert:
            self.providers.database.relational.upsert_documents_overview(
                documents_to_upsert
            )

        # TODO - modify ingestion service so that at end we write out number
        # of vectors produced or the error message to document info
        # THEN, return updated document infos here
        return {
            "processed_documents": [
                document
                for document in document_infos
                if document.id in successful_ids
            ],
            "failed_documents": [
                {
                    "document_id": document_id,
                    "result": str(results[document_id]),
                }
                for document_id in failed_ids
            ],
            "skipped_documents": skipped_ids,
        }
