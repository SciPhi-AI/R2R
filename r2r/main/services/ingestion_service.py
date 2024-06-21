import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, List, Optional, Union

from fastapi import Form, HTTPException, UploadFile

from r2r.core import (
    Document,
    DocumentInfo,
    DocumentType,
    KVLoggingSingleton,
    RunManager,
    generate_id_from_label,
    increment_version,
    to_async_generator,
)
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import (
    R2RIngestFilesRequest,
    R2RPipelines,
    R2RProviders,
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
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config, providers, pipelines, run_manager, logging_connection
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
            raise HTTPException(
                status_code=400, detail="No documents provided for ingestion."
            )

        document_infos = []
        skipped_documents = []
        processed_documents = []

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
                    raise HTTPException(
                        status_code=409,
                        detail=f"Document with ID {document.id} already exists.",
                    )
                skipped_documents.append(
                    document.metadata.get("title", None) or str(document.id)
                )
                continue

            document_title = document.metadata.get("title", None)
            document_user_id = document.metadata.get("user_id", None)

            now = datetime.now()
            document_infos.append(
                DocumentInfo(
                    **{
                        "document_id": document.id,
                        "version": version,
                        "size_in_bytes": len(document.data),
                        "metadata": document.metadata.copy(),
                        "title": document_title,
                        "user_id": document_user_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            )

            processed_documents.append(document_title or str(document.id))

        if skipped_documents and len(skipped_documents) == len(documents):
            logger.error("All provided documents already exist.")
            raise HTTPException(
                status_code=409,
                detail="All provided documents already exist. Use the update endpoint to update these documents.",
            )

        if skipped_documents:
            logger.warning(
                f"Skipped ingestion for the following documents since they already exist: {', '.join(skipped_documents)}. Use the update endpoint to update these documents."
            )

        await self.pipelines.ingestion_pipeline.run(
            input=to_async_generator(
                [
                    doc
                    for it, doc in enumerate(documents)
                    if doc.id not in existing_document_info
                    or (
                        doc.id
                        and (
                            versions
                            and existing_document_info[doc.id].version
                            != versions[it]
                        )
                    )
                ]
            ),
            versions=[
                info.version
                for info in document_infos
                if info.created_at == info.updated_at
            ],
            run_manager=self.run_manager,
        )

        self.providers.vector_db.upsert_documents_overview(document_infos)
        return {
            "processed_documents": [
                f"Document '{title}' processed successfully."
                for title in processed_documents
            ],
            "skipped_documents": [
                f"Document '{title}' skipped since it already exists."
                for title in skipped_documents
            ],
        }

    @telemetry_event("UpdateDocuments")
    async def update_documents(
        self,
        documents: List[Document],
        metadatas: Optional[List[dict]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if len(documents) == 0:
            raise HTTPException(
                status_code=400, detail="No documents provided for update."
            )

        old_versions = []
        new_versions = []
        document_infos_modified = []

        documents_overview = await self._documents_overview(
            document_ids=[doc.id for doc in documents]
        )

        for iteration, doc in enumerate(documents):
            document_info = documents_overview[iteration]
            current_version = document_info.version
            old_versions.append(current_version)
            new_versions.append(increment_version(current_version))

            document_metadata = (
                metadatas[iteration] if metadatas else doc.metadata
            )
            document_metadata["title"] = document_metadata.get(
                "title", None
            ) or document_metadata.get("title", None)
            document_infos_modified.append(
                DocumentInfo(
                    **{
                        "document_id": doc.id,
                        "version": new_versions[-1],
                        "size_in_bytes": len(doc.data),
                        "metadata": document_metadata.copy(),
                        "title": document_metadata["title"],
                        "user_id": document_metadata.get("user_id", None),
                        "created_at": document_info.created_at,
                        "updated_at": datetime.now(),
                    }
                )
            )

        await self.ingest_documents(documents, versions=new_versions)

        for doc, old_version in zip(documents, old_versions):
            await self._delete(
                ["document_id", "version"], [str(doc.id), old_version]
            )

        self.providers.vector_db.upsert_documents_overview(
            document_infos_modified
        )
        document_ids = ",".join([str(doc.id) for doc in documents])
        return {"results": f"Document(s) {document_ids} updated."}

    @telemetry_event("IngestFiles")
    async def ingest_files(
        self,
        files: List[UploadFile],
        metadatas: Optional[List[dict]] = None,
        document_ids: Optional[List[uuid.UUID]] = None,
        user_ids: Optional[List[Optional[uuid.UUID]]] = None,
        versions: Optional[List[str]] = None,
        skip_document_info: bool = False,
        *args: Any,
        **kwargs: Any,
    ):
        if metadatas and len(metadatas) != len(files):
            raise ValueError(
                "Number of metadata entries does not match number of files."
            )
        if document_ids and len(document_ids) != len(files):
            raise ValueError(
                "Number of document id entries does not match number of files."
            )
        elif document_ids and not all(
            isinstance(doc_id, uuid.UUID) for doc_id in document_ids
        ):
            raise ValueError("All document IDs must be of type UUID.")
        if user_ids and len(user_ids) != len(files):
            raise ValueError(
                "Number of user_ids entries does not match number of files."
            )
        elif user_ids and not all(
            (isinstance(user_id, uuid.UUID) for user_id in user_ids if user_id)
        ):
            raise ValueError("All user IDs must be of type UUID.")
        if len(files) == 0:
            raise HTTPException(
                status_code=400, detail="No files provided for ingestion."
            )

        try:
            documents = []
            document_infos = []
            skipped_documents = []
            processed_documents = []
            existing_document_info = {
                doc_info.document_id: doc_info
                for doc_info in self.providers.vector_db.get_documents_overview()
            }
            for iteration, file in enumerate(files):
                logger.info(f"Processing file: {file.filename}")
                if (
                    file.size
                    > self.config.app.get("max_file_size_in_mb", 32)
                    * MB_CONVERSION_FACTOR
                ):
                    logger.error(f"File size exceeds limit: {file.filename}")
                    raise HTTPException(
                        status_code=413,
                        detail="File size exceeds maximum allowed size.",
                    )
                if not file.filename:
                    logger.error("File name not provided.")
                    raise HTTPException(
                        status_code=400, detail="File name not provided."
                    )

                file_extension = file.filename.split(".")[-1].lower()
                excluded_parsers = self.config.ingestion.get(
                    "excluded_parsers", {}
                )
                if file_extension.upper() not in DocumentType.__members__:
                    logger.error(
                        f"'{file_extension}' is not a valid DocumentType"
                    )
                    raise HTTPException(
                        status_code=415,
                        detail=f"'{file_extension}' is not a valid DocumentType.",
                    )
                if DocumentType[file_extension.upper()] in excluded_parsers:
                    logger.error(
                        f"{file_extension} is explicitly excluded in the configuration file."
                    )
                    raise HTTPException(
                        status_code=415,
                        detail=f"{file_extension} is explicitly excluded in the configuration file.",
                    )
                document_metadata = metadatas[iteration] if metadatas else {}

                document_title = (
                    document_metadata.get("title", None)
                    or file.filename.split(os.path.sep)[-1]
                )
                document_metadata["title"] = document_title
                document_id = (
                    generate_id_from_label(document_title)
                    if document_ids is None
                    else document_ids[iteration]
                )

                version = versions[iteration] if versions else "v0"
                if document_id in existing_document_info and (
                    versions is None
                    or existing_document_info[document_id] == version
                ):
                    logger.error(f"File with ID {document_id} already exists.")
                    if len(files) == 1:
                        raise HTTPException(
                            status_code=409,
                            detail=f"File with ID {document_id} already exists.",
                        )
                    skipped_documents.append(file.filename)
                    continue

                file_content = await file.read()
                logger.info(f"File read successfully: {file.filename}")

                user_id = user_ids[iteration] if user_ids else None
                if user_id:
                    document_metadata["user_id"] = str(user_id)
                version = versions[iteration] if versions else "v0"
                now = datetime.now()

                documents.append(
                    Document(
                        id=document_id,
                        type=DocumentType[file_extension.upper()],
                        data=file_content,
                        metadata=document_metadata,
                        title=document_title,
                        user_ids=user_id,
                    )
                )
                document_infos.append(
                    DocumentInfo(
                        **{
                            "document_id": document_id,
                            "version": version,
                            "size_in_bytes": len(file_content),
                            "metadata": document_metadata.copy(),
                            "title": document_title,
                            "user_id": user_id,
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                )

                processed_documents.append(file.filename)

            if skipped_documents and len(skipped_documents) == len(files):
                logger.error("All uploaded documents already exist.")
                raise HTTPException(
                    status_code=409,
                    detail="All uploaded documents already exist. Use the update endpoint to update these documents.",
                )

            if skipped_documents:
                logger.warning(
                    f"Skipped ingestion for the following documents since they already exist: {', '.join(skipped_documents)}. Use the update endpoint to update these documents."
                )

            await self.pipelines.ingestion_pipeline.run(
                input=to_async_generator(documents),
                versions=versions,
                run_manager=self.run_manager,
            )

            if not skip_document_info:
                self.providers.vector_db.upsert_documents_overview(
                    document_infos
                )

            return {
                "processed_documents": [
                    f"File '{filename}' processed successfully."
                    for filename in processed_documents
                ],
                "skipped_documents": [
                    f"File '{filename}' skipped since it already exists."
                    for filename in skipped_documents
                ],
            }
        except Exception as e:
            raise e
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
            raise HTTPException(
                status_code=400, detail="No files provided for update."
            )

        try:
            if len(document_ids) != len(files):
                raise HTTPException(
                    status_code=400,
                    detail="Number of ids does not match number of files.",
                )

            if metadatas and len(metadatas) != len(files):
                raise HTTPException(
                    status_code=400,
                    detail="Number of metadata entries does not match number of files.",
                )

            old_versions = []
            new_versions = []
            documents_overview = await self._documents_overview(
                document_ids=document_ids
            )
            documents_overview_modified = []
            if len(documents_overview) != len(files):
                raise HTTPException(
                    status_code=404,
                    detail="One or more documents was not found.",
                )
            for it, document_info in enumerate(documents_overview):
                if not document_info:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Document with id {document_ids[it]} not found.",
                    )

                current_version = document_info.version
                old_versions.append(current_version)
                new_version = increment_version(current_version)
                new_versions.append(new_version)
                document_info.version = new_version
                document_info.metadata = (
                    metadatas[it] if metadatas else document_info.metadata
                )
                document_info.size_in_bytes = files[it].size
                document_info.updated_at = datetime.now()

                title = files[it].filename.split(os.path.sep)[-1]
                document_info.metadata["title"] = (
                    document_info.metadata.get("title", None) or title
                )

                documents_overview_modified.append(document_info)
            await self.ingest_files(
                files,
                [ele.metadata for ele in documents_overview_modified],
                document_ids,
                versions=new_versions,
            )

            for id, old_version in zip(document_ids, old_versions):
                await self._delete(
                    ["document_id", "version"], [str(id), old_version]
                )

            self.providers.vector_db.upsert_documents_overview(
                documents_overview_modified
            )
            document_ids = ",".join([str(doc_id) for doc_id in document_ids])
            return {
                "results": f"Document(s) with IDs {document_ids} updated successfully."
            }
        except Exception as e:
            logger.error(f"update_files(files={files}) - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            for file in files:
                file.file.close()

    @staticmethod
    def parse_ingest_files_form_data(
        metadatas: Optional[str] = Form(None),
        document_ids: str = Form(None),
        user_ids: str = Form(None),
        versions: Optional[str] = Form(None),
        skip_document_info: bool = Form(None),
    ) -> R2RIngestFilesRequest:
        try:
            request_data = {
                "metadatas": (
                    json.loads(metadatas)
                    if metadatas and metadatas != "null"
                    else None
                ),
                "document_ids": (
                    [uuid.UUID(doc_id) for doc_id in json.loads(document_ids)]
                    if document_ids and document_ids != "null"
                    else None
                ),
                "user_ids": (
                    [
                        uuid.UUID(user_id) if user_id else None
                        for user_id in json.loads(user_ids)
                    ]
                    if user_ids and user_ids != "null"
                    else None
                ),
                "versions": (
                    json.loads(versions)
                    if versions and versions != "null"
                    else None
                ),
                "skip_document_info": skip_document_info,
            }
            return R2RIngestFilesRequest(**request_data)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid form data: {e}"
            )

    @staticmethod
    def parse_update_files_form_data(
        metadatas: Optional[str] = Form(None),
        document_ids: str = Form(...),
    ) -> R2RUpdateFilesRequest:
        try:
            request_data = {
                "metadatas": (
                    json.loads(metadatas)
                    if metadatas and metadatas != "null"
                    else None
                ),
                "document_ids": (
                    [uuid.UUID(doc_id) for doc_id in json.loads(document_ids)]
                    if document_ids and document_ids != "null"
                    else None
                ),
            }
            return R2RUpdateFilesRequest(**request_data)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid form data: {e}"
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
            raise HTTPException(
                status_code=404, detail="No entries found for deletion."
            )
        self.providers.vector_db.delete_documents_overview(ids)
        return {"results": "Entries deleted successfully."}
