import json
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
from core.base.providers import ChunkingProvider, ChunkingConfig
from core.telemetry.telemetry_decorator import telemetry_event

from ...base.api.models.auth.responses import UserResponse
from ..abstractions import R2RAgents, R2RPipelines, R2RProviders
from ..config import R2RConfig
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
        file_data: list[dict],  # Changed from list[UploadFile] to list[dict]
        user: UserResponse,
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[UUID]] = None,
        chunking_config: Optional[ChunkingConfig] = None,
        *args: Any,
        **kwargs: Any,
    ) -> IngestionResponse:
        if not file_data:
            raise R2RException(
                status_code=400, message="No files provided for ingestion."
            )
        if len(file_data) > MAX_FILES_PER_INGESTION:
            raise R2RException(
                status_code=400,
                message=f"Exceeded maximum number of files per ingestion: {MAX_FILES_PER_INGESTION}.",
            )
        try:
            from ..assembly.factory import R2RProviderFactory

            documents = []
            for iteration, file_info in enumerate(file_data):
                if not file_info.get('filename'):
                    raise R2RException(
                        status_code=400, message="File name not provided."
                    )
                
                chunking_provider = None
                if chunking_config:
                    chunking_config.validate()
                    # Validate the chunking settings
                    chunking_provider = R2RProviderFactory.create_chunking_provider(
                        chunking_config
                    )
                document_metadata = metadatas[iteration] if metadatas else {}

                # document id is dynamically generated from the filename and user id, unless explicitly provided
                document_id = (
                    document_ids[iteration]
                    if document_ids
                    else generate_user_document_id(file_info['filename'], user.id)
                )
                document = self._file_data_to_document(
                    file_info, user, document_id, document_metadata
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
            # No need to close files here as we're not dealing with file objects directly
            pass

    def _file_data_to_document(
        self,
        file_info: dict,
        user: UserResponse,
        document_id: UUID,
        metadata: dict,
    ) -> Document:
        file_extension = file_info['filename'].split(".")[-1].lower()
        if file_extension.upper() not in DocumentType.__members__:
            raise R2RException(
                status_code=415,
                message=f"'{file_extension}' is not a valid DocumentType.",
            )

        document_title = metadata.get("title") or file_info['filename'].split("/")[-1]
        metadata["title"] = document_title

        return Document(
            id=document_id,
            group_ids=metadata.get("group_ids", []),
            user_id=user.id,
            type=DocumentType[file_extension.upper()],
            data=file_info['content'],  # Assuming the file content is passed as base64 or similar
            metadata=metadata,
        )

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

        # # TODO - modify ingestion service so that at end we write out number
        # # of vectors produced or the error message to document info
        # # THEN, return updated document infos here
        # return {
        #     "processed_documents": [
        #         document
        #         for document in document_infos
        #         if document.id in successful_ids
        #     ],
        #     "failed_documents": [
        #         {
        #             "document_id": document_id,
        #             "result": str(results[document_id]),
        #         }
        #         for document_id in failed_ids
        #     ],
        #     "skipped_documents": skipped_ids,
        # }
        return True


class IngestionServiceAdapter:
    @staticmethod
    def prepare_ingest_files_input(
        file_data: list[dict],
        user: UserResponse,
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[UUID]] = None,
        chunking_config: Optional[ChunkingConfig] = None,
    ) -> dict:
        return {
            "file_data": file_data,
            "user": user.to_dict(),
            "metadatas": metadatas,
            "document_ids": [str(doc_id) for doc_id in document_ids] if document_ids else None,
            "chunking_config": chunking_config.to_dict() if chunking_config else None,
        }

    @staticmethod
    def parse_ingest_files_input(data: dict):
        user_data = data["user"]
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid user data format: {user_data}")
        
        return {
            "file_data": data["file_data"],
            "user": UserResponse.from_dict(user_data),
            "metadatas": data["metadatas"],
            "document_ids": [UUID(doc_id) for doc_id in data["document_ids"]] if data["document_ids"] else None,
            "chunking_config": ChunkingConfig.from_dict(data["chunking_config"]) if data["chunking_config"] else None,
        }

    # @staticmethod
    # def serialize_ingestion_response(response: dict) -> dict:
    #     return {
    #         "processed_documents": [doc.to_dict() for doc in response["processed_documents"]],
    #         "failed_documents": response["failed_documents"],
    #         "skipped_documents": [str(doc_id) for doc_id in response["skipped_documents"]],
    #     }