import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from fastapi import Form, UploadFile

from r2r.base import (
    Document,
    DocumentInfo,
    DocumentType,
    KVLoggingSingleton,
    R2RDocumentProcessingError,
    R2RException,
    RunManager,
    User,
    generate_id_from_label,
    increment_version,
    to_async_generator,
)
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAssistants, R2RPipelines, R2RProviders
from ..api.routes.ingestion.requests import (
    R2RIngestFilesRequest,
    R2RUpdateFilesRequest,
)
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)
MB_CONVERSION_FACTOR = 1024 * 1024


class IngestionService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        assistants: R2RAssistants,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )

    def _file_to_document(
        self, file: UploadFile, document_id: uuid.UUID, metadata: dict
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
            type=DocumentType[file_extension.upper()],
            data=file.file.read(),
            metadata=metadata,
        )

    @telemetry_event("IngestDocuments")
    async def ingest_documents(
        self,
        documents: list[Document],
        versions: Optional[list[str]] = None,
        user: Optional[User] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if len(documents) == 0:
            raise R2RException(
                status_code=400, message="No documents provided for ingestion."
            )

        document_infos = []
        skipped_documents = []
        processed_documents = {}
        duplicate_documents = defaultdict(list)
        user_ids = [str(user.id)] if user else []

        existing_documents = (
            (
                self.providers.database.relational.get_documents_overview(
                    filter_user_ids=user_ids
                )
            )
            if self.providers.database
            else []
        )

        existing_document_info = {
            doc_info.document_id: doc_info for doc_info in existing_documents
        }

        for iteration, document in enumerate(documents):
            version = versions[iteration] if versions else "v0"

            # Check if user ID has already been provided, and if it matches the authenticated user
            user_id = document.metadata.get("user_id", None)
            if user:
                if user_id and user_id != str(user.id):
                    raise R2RException(
                        status_code=403,
                        message="User ID in metadata does not match authenticated user.",
                    )
                document.metadata["user_id"] = str(user.id)

            # Check for duplicates within the current batch
            if document.id in processed_documents:
                duplicate_documents[document.id].append(
                    document.metadata.get("title", str(document.id))
                )
                continue

            if (
                document.id in existing_document_info
                and existing_document_info[document.id].version == version
                and existing_document_info[document.id].status == "success"
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
                    (
                        document.id,
                        document.metadata.get("title", None)
                        or str(document.id),
                    )
                )
                continue

            now = datetime.now()
            document_info_metadata = document.metadata.copy()
            title = document_info_metadata.pop("title", str(document.id))
            user_id = document_info_metadata.pop("user_id", None)
            document_infos.append(
                DocumentInfo(
                    document_id=document.id,
                    version=version,
                    size_in_bytes=len(document.data),
                    metadata=document_info_metadata,
                    title=title,
                    user_id=user_id,
                    created_at=now,
                    updated_at=now,
                    status="processing",  # Set initial status to `processing`
                )
            )

            processed_documents[document.id] = document.metadata.get(
                "title", str(document.id)
            )

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
                message="All provided documents already exist. Use the `update_documents` endpoint instead to update these documents.",
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
                    not in [skipped[0] for skipped in skipped_documents]
                ]
            ),
            versions=[info.version for info in document_infos],
            run_manager=self.run_manager,
            *args,
            **kwargs,
        )
        return await self._process_ingestion_results(
            ingestion_results,
            document_infos,
            skipped_documents,
            processed_documents,
        )

    @telemetry_event("IngestFiles")
    async def ingest_files(
        self,
        files: list[UploadFile],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[uuid.UUID]] = None,
        versions: Optional[list[str]] = None,
        user: Optional[User] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if not files:
            raise R2RException(
                status_code=400, message="No files provided for ingestion."
            )

        try:
            documents = []
            for iteration, file in enumerate(files):
                if not file.filename:
                    raise R2RException(
                        status_code=400, message="File name not provided."
                    )

                document_metadata = metadatas[iteration] if metadatas else {}

                id_label = str(file.filename.split("/")[-1])
                # Make user-level ids unique
                if user:
                    id_label += str(user.id)
                document_id = (
                    document_ids[iteration]
                    if document_ids
                    else generate_id_from_label(id_label)
                )

                document = self._file_to_document(
                    file, document_id, document_metadata
                )
                documents.append(document)
            return await self.ingest_documents(
                documents, versions, *args, **kwargs, user=user
            )

        finally:
            for file in files:
                file.file.close()

    @telemetry_event("UpdateFiles")
    async def update_files(
        self,
        files: list[UploadFile],
        document_ids: list[uuid.UUID],
        metadatas: Optional[list[dict]] = None,
        user: Optional[User] = None,
        *args: Any,
        **kwargs: Any,
    ):
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
            if len(document_ids) != len(files):
                raise R2RException(
                    status_code=400,
                    message="Number of ids does not match number of files.",
                )

            documents_overview = (
                self.providers.database.relational.get_documents_overview(
                    filter_document_ids=[
                        str(doc_id) for doc_id in document_ids
                    ]
                )
            )

            if len(documents_overview) != len(files):
                raise R2RException(
                    status_code=404,
                    message="One or more documents was not found.",
                )

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

                user_id = doc_info.metadata.get("user_id", None)
                if user:
                    if user_id and user_id != str(user.id):
                        raise R2RException(
                            status_code=403,
                            message="User ID in metadata does not match authenticated user.",
                        )
                    doc_info.metadata["user_id"] = str(user.id)

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
                    file, doc_id, updated_metadata
                )
                documents.append(document)

            ingestion_results = await self.ingest_documents(
                documents, versions=new_versions, user=user, *args, **kwargs
            )

            for doc_id, old_version in zip(
                document_ids,
                [doc_info.version for doc_info in documents_overview],
            ):
                keys = ["document_id", "version"]
                values = [str(doc_id), old_version]
                if user:
                    keys.append("user_id")
                    values.append(str(user.id))

                self.providers.database.vector.delete_by_metadata(keys, values)
                self.providers.database.relational.delete_from_documents_overview(
                    doc_id, old_version
                )

            return ingestion_results

        finally:
            for file in files:
                file.file.close()

    async def _process_ingestion_results(
        self,
        ingestion_results: dict,
        document_infos: list[DocumentInfo],
        skipped_documents: list[tuple[str, str]],
        processed_documents: dict,
    ):
        skipped_ids = [ele[0] for ele in skipped_documents]
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
            if document_info.document_id not in skipped_ids:
                if document_info.document_id in failed_ids:
                    document_info.status = "failure"
                elif document_info.document_id in successful_ids:
                    document_info.status = "success"
                documents_to_upsert.append(document_info)

        if documents_to_upsert:
            self.providers.database.relational.upsert_documents_overview(
                documents_to_upsert
            )

        results = {
            "processed_documents": [
                f"Document '{processed_documents[document_id]}' processed successfully."
                for document_id in successful_ids
            ],
            "failed_documents": [
                f"Document '{processed_documents[document_id]}': {results[document_id]}"
                for document_id in failed_ids
            ],
            "skipped_documents": [
                f"Document '{filename}' skipped since it already exists."
                for _, filename in skipped_documents
            ],
        }

        # TODO - Clean up logging for document parse results
        if run_ids := list(self.run_manager.run_info.keys()):
            run_id = run_ids[0]
            for key in results:
                if key in ["processed_documents", "failed_documents"]:
                    for value in results[key]:
                        await self.logging_connection.log(
                            log_id=run_id,
                            key="document_parse_result",
                            value=value,
                        )
        return results

    @staticmethod
    def parse_ingest_files_form_data(
        metadatas: Optional[str] = Form(None),
        document_ids: str = Form(None),
        versions: Optional[str] = Form(None),
    ) -> R2RIngestFilesRequest:
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

            request_data = {
                "metadatas": parsed_metadatas,
                "document_ids": parsed_document_ids,
                "versions": parsed_versions,
            }
            return R2RIngestFilesRequest(**request_data)
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
        metadatas: Optional[str] = Form(None),
        document_ids: str = Form(...),
    ) -> R2RUpdateFilesRequest:
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

            request_data = {
                "metadatas": parsed_metadatas,
                "document_ids": parsed_document_ids,
            }
            return R2RUpdateFilesRequest(**request_data)
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
