import json
import logging
import uuid
from datetime import datetime
from typing import Any, List, Optional, Union

from fastapi import Form, UploadFile

from r2r.base import (
    Document,
    DocumentInfo,
    DocumentType,
    KVLoggingSingleton,
    R2RDocumentProcessingError,
    R2RException,
    RunManager,
    generate_id_from_label,
    increment_version,
    to_async_generator,
)
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RPipelines, R2RProviders
from ..api.requests import R2RIngestFilesRequest, R2RUpdateFilesRequest
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
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config, providers, pipelines, run_manager, logging_connection
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

        document_title = (
            metadata.get("title", None) or file.filename.split("/")[-1]
        )
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
        documents: List[Document],
        versions: Optional[List[str]] = None,
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

        existing_document_info = {
            doc_info.document_id: doc_info
            for doc_info in self.providers.vector_db.get_documents_overview()
        }

        for iteration, document in enumerate(documents):
            version = versions[iteration] if versions else "v0"
            if (
                document.id in existing_document_info
                and existing_document_info[document.id].version == version
            ):
                logger.error(f"Document with ID {document.id} already exists.")
                if len(documents) == 1:
                    raise R2RException(
                        status_code=409,
                        message=f"Document with ID {document.id} already exists.",
                    )
                skipped_documents.append(
                    (
                        str(document.id),
                        document.metadata.get("title", None)
                        or str(document.id),
                    )
                )
                continue

            now = datetime.now()
            document_infos.append(
                DocumentInfo(
                    document_id=document.id,
                    version=version,
                    size_in_bytes=len(document.data),
                    metadata=document.metadata.copy(),
                    title=document.metadata.get("title", str(document.id)),
                    user_id=document.metadata.get("user_id", None),
                    created_at=now,
                    updated_at=now,
                )
            )

            processed_documents[document.id] = document.metadata.get(
                "title", str(document.id)
            )

        if skipped_documents and len(skipped_documents) == len(documents):
            logger.error("All provided documents already exist.")
            raise R2RException(
                status_code=409,
                message="All provided documents already exist. Use the `update_documents` endpoint instead to update these documents.",
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

        return self._process_ingestion_results(
            ingestion_results,
            document_infos,
            skipped_documents,
            processed_documents,
        )

    @telemetry_event("IngestFiles")
    async def ingest_files(
        self,
        files: List[UploadFile],
        metadatas: Optional[List[dict]] = None,
        document_ids: Optional[List[uuid.UUID]] = None,
        versions: Optional[List[str]] = None,
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
                logger.info(f"Processing file: {file.filename}")
                if (
                    file.size
                    > self.config.app.get("max_file_size_in_mb", 32)
                    * MB_CONVERSION_FACTOR
                ):
                    raise R2RException(
                        status_code=413,
                        message=f"File size exceeds maximum allowed size: {file.filename}",
                    )
                if not file.filename:
                    raise R2RException(
                        status_code=400, message="File name not provided."
                    )

                document_metadata = metadatas[iteration] if metadatas else {}
                document_id = (
                    document_ids[iteration]
                    if document_ids
                    else generate_id_from_label(file.filename.split("/")[-1])
                )

                document = self._file_to_document(
                    file, document_id, document_metadata
                )
                documents.append(document)

            return await self.ingest_documents(
                documents, versions, *args, **kwargs
            )

        finally:
            for file in files:
                file.file.close()

    @telemetry_event("UpdateFiles")
    async def update_files(
        self,
        files: List[UploadFile],
        document_ids: List[uuid.UUID],
        metadatas: Optional[List[dict]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if not files:
            raise R2RException(
                status_code=400, message="No files provided for update."
            )

        try:
            if len(document_ids) != len(files):
                raise R2RException(
                    status_code=400,
                    message="Number of ids does not match number of files.",
                )

            documents_overview = await self._documents_overview(
                document_ids=document_ids
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
                documents, versions=new_versions, *args, **kwargs
            )

            for doc_id, old_version in zip(
                document_ids,
                [doc_info.version for doc_info in documents_overview],
            ):
                await self._delete(
                    ["document_id", "version"], [str(doc_id), old_version]
                )

            return f"Documents updated: {ingestion_results['processed_documents']}\nFailed updates: {ingestion_results['failed_documents']}"

        finally:
            for file in files:
                file.file.close()

    def _process_ingestion_results(
        self,
        ingestion_results,
        document_infos,
        skipped_documents,
        processed_documents,
    ):
        skipped_ids = [ele[0] for ele in skipped_documents]
        failed_ids = []

        results = {}
        if ingestion_results["embedding_pipeline_output"]:
            results = {
                k: v for k, v in ingestion_results["embedding_pipeline_output"]
            }
            for _, error in results.items():
                if isinstance(error, R2RDocumentProcessingError):
                    logger.error(
                        f"Error processing document with ID {error.document_id}: {error.message}"
                    )
                    failed_ids.append(error.document_id)

        documents_to_upsert = [
            document_info
            for document_info in document_infos
            if document_info.document_id not in skipped_ids
            and document_info.document_id not in failed_ids
        ]
        if documents_to_upsert:
            self.providers.vector_db.upsert_documents_overview(
                documents_to_upsert
            )

        return {
            "processed_documents": [
                f"Document '{processed_documents[document_id]}' processed successfully."
                for document_id in processed_documents.keys()
                if document_id not in failed_ids
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

    # TODO - Move to mgmt service for document info, delete, post orchestration buildout
    async def _documents_overview(
        self,
        document_ids: Optional[list[uuid.UUID]] = None,
        user_ids: Optional[list[uuid.UUID]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return self.providers.vector_db.get_documents_overview(
            filter_document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            filter_user_ids=(
                [str(ele) for ele in user_ids] if user_ids else None
            ),
        )

    async def _delete(
        self, keys: list[str], values: list[Union[bool, int, str]]
    ):
        logger.info(
            f"Deleting documents which match on these keys and values: ({keys}, {values})"
        )

        ids = self.providers.vector_db.delete_by_metadata(keys, values)
        if not ids:
            raise R2RException(
                status_code=404, message="No entries found for deletion."
            )
        self.providers.vector_db.delete_documents_overview(ids)
        return "Entries deleted successfully."
