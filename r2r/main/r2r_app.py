import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Optional, Union

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from r2r.core import (
    AnalysisTypes,
    Document,
    DocumentInfo,
    DocumentType,
    FilterCriteria,
    GenerationConfig,
    KVLoggingSingleton,
    LogProcessor,
    RunManager,
    generate_id_from_label,
    increment_version,
    manage_run,
    to_async_generator,
)
from r2r.pipes import R2REvalPipe
from r2r.telemetry.telemetry_decorator import telemetry_event

from .r2r_abstractions import R2RPipelines, R2RProviders
from .r2r_config import R2RConfig

MB_CONVERSION_FACTOR = 1024 * 1024

logger = logging.getLogger(__name__)


def syncable(func):
    """Decorator to mark methods for synchronous wrapper creation."""
    func._syncable = True
    return func


class AsyncSyncMeta(type):
    _event_loop = None  # Class-level shared event loop

    @classmethod
    def get_event_loop(cls):
        if cls._event_loop is None or cls._event_loop.is_closed():
            cls._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(cls._event_loop)
        return cls._event_loop

    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)
        for attr_name, attr_value in dct.items():
            if asyncio.iscoroutinefunction(attr_value) and getattr(
                attr_value, "_syncable", False
            ):
                sync_method_name = attr_name[
                    1:
                ]  # Remove leading 'a' for sync method
                async_method = attr_value

                def make_sync_method(async_method):
                    def sync_wrapper(self, *args, **kwargs):
                        loop = cls.get_event_loop()
                        if not loop.is_running():
                            # Setup to run the loop in a background thread if necessary
                            # to prevent blocking the main thread in a synchronous call environment
                            from threading import Thread

                            result = None
                            exception = None

                            def run():
                                nonlocal result, exception
                                try:
                                    asyncio.set_event_loop(loop)
                                    result = loop.run_until_complete(
                                        async_method(self, *args, **kwargs)
                                    )
                                except Exception as e:
                                    exception = e
                                finally:
                                    generation_config = kwargs.get(
                                        "rag_generation_config", None
                                    )
                                    if (
                                        not generation_config
                                        or not generation_config.stream
                                    ):
                                        loop.run_until_complete(
                                            loop.shutdown_asyncgens()
                                        )
                                        loop.close()

                            thread = Thread(target=run)
                            thread.start()
                            thread.join()
                            if exception:
                                raise exception
                            return result
                        else:
                            # If there's already a running loop, schedule and execute the coroutine
                            future = asyncio.run_coroutine_threadsafe(
                                async_method(self, *args, **kwargs), loop
                            )
                            return future.result()

                    return sync_wrapper

                setattr(
                    new_cls, sync_method_name, make_sync_method(async_method)
                )
        return new_cls


class R2RApp(metaclass=AsyncSyncMeta):
    """Main class for the R2R application.

    This class is responsible for setting up the FastAPI application and
    defining the routes for the various endpoints. It also contains the
    synchronous wrappers for the asynchronous methods defined in the class.

    Endpoints are provided to:
    - Ingest documents
    - Ingest files
    - Search
    - Retrieve and generate completions
    - Delete entries
    - Retrieve user IDs
    - Retrieve user document data
    - Retrieve logs
    - Retrieve analytics
    """

    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: Optional[RunManager] = None,
        do_apply_cors: bool = True,
        *args,
        **kwargs,
    ):
        self.config = config
        self.providers = providers
        self.logging_connection = KVLoggingSingleton()
        self.ingestion_pipeline = pipelines.ingestion_pipeline
        self.search_pipeline = pipelines.search_pipeline
        self.rag_pipeline = pipelines.rag_pipeline
        self.streaming_rag_pipeline = pipelines.streaming_rag_pipeline
        self.eval_pipeline = pipelines.eval_pipeline
        self.run_manager = run_manager or RunManager(self.logging_connection)
        self.app = FastAPI()

        self._setup_routes()
        if do_apply_cors:
            self._apply_cors()

    def _setup_routes(self):
        # Ingestion
        self.app.add_api_route(
            path="/update_prompt",
            endpoint=self.update_prompt_app,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/ingest_documents",
            endpoint=self.ingest_documents_app,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/update_documents",
            endpoint=self.update_documents_app,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/ingest_files",
            endpoint=self.ingest_files_app,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/update_files",
            endpoint=self.update_files_app,
            methods=["POST"],
        )

        # RAG & Eval
        self.app.add_api_route(
            path="/search", endpoint=self.search_app, methods=["POST"]
        )
        self.app.add_api_route(
            path="/rag", endpoint=self.rag_app, methods=["POST"]
        )
        self.app.add_api_route(
            path="/evaluate",
            endpoint=self.evaluate_app,
            methods=["POST"],
        )

        # Logging & Analytics
        self.app.add_api_route(
            path="/logs",
            endpoint=self.logs_app,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/analytics", endpoint=self.analytics_app, methods=["POST"]
        )

        # Document & User Management
        self.app.add_api_route(
            path="/users_stats",
            endpoint=self.users_stats_app,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/documents_info",
            endpoint=self.documents_info_app,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/document_chunks",
            endpoint=self.document_chunks_app,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/delete", endpoint=self.delete_app, methods=["DELETE"]
        )

        # Other
        self.app.add_api_route(
            path="/app_settings",
            endpoint=self.app_settings_app,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/openapi_spec",
            endpoint=self.openapi_spec_app,
            methods=["GET"],
        )

    @syncable
    async def aupsert_prompt(
        self, name: str, template: str, input_types: dict
    ):
        """Upsert a prompt into the system."""
        self.providers.prompt.add_prompt(name, template, input_types)
        return {"results": f"Prompt '{name}' added successfully."}

    class UpdatePromptRequest(BaseModel):
        name: str
        template: Optional[str] = None
        input_types: Optional[dict[str, str]] = None

    @telemetry_event("UpdatePrompt")
    async def update_prompt_app(self, request: UpdatePromptRequest):
        """Update a prompt's template and/or input types."""
        try:
            return await self.aupsert_prompt(
                request.name, request.template, request.input_types
            )
        except Exception as e:
            logger.error(
                f"update_prompt_app(name={request.name}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def aingest_documents(
        self,
        documents: list[Document],
        metadatas: Optional[list[dict]] = None,
        versions: Optional[list[str]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if metadatas and len(metadatas) != len(documents):
            raise ValueError(
                "Number of metadata entries does not match number of documents."
            )
        if len(documents) == 0:
            raise HTTPException(
                status_code=400, detail="No documents provided for ingestion."
            )

        document_infos = []
        skipped_documents = []
        processed_documents = []
        existing_document_ids = [
            str(doc_info.document_id)
            for doc_info in self.providers.vector_db.get_documents_info()
        ]
        version = versions[iteration] if versions else "v0"

        for iteration, document in enumerate(documents):
            if (
                version is not None
                and str(document.id) in existing_document_ids
            ):
                logger.error(f"Document with ID {document.id} already exists.")
                if len(documents) == 1:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Document with ID {document.id} already exists.",
                    )
                skipped_documents.append(document.title or str(document.id))
                continue

            document_metadata = (
                metadatas[iteration] if metadatas else document.metadata
            )
            document_title = (
                document_metadata.get("title", None) or document.title
            )
            document_metadata["title"] = document_title

            if document.user_id:
                document_metadata["user_id"] = str(document.user_id)
            document.metadata = document_metadata

            now = datetime.now()
            version = versions[iteration] if versions else "v0"
            document_infos.append(
                DocumentInfo(
                    **{
                        "document_id": document.id,
                        "version": version,
                        "size_in_bytes": len(document.data),
                        "metadata": document_metadata.copy(),
                        "title": document_title,
                        "user_id": document.user_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            )

            processed_documents.append(document.title or str(document.id))

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

        await self.ingestion_pipeline.run(
            input=to_async_generator(
                [
                    doc
                    for doc in documents
                    if str(doc.id) not in existing_document_ids
                ]
            ),
            versions=[
                info.version
                for info in document_infos
                if info.created_at == info.updated_at
            ],
            run_manager=self.run_manager,
        )

        self.providers.vector_db.upsert_documents_info(document_infos)
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

    class IngestDocumentsRequest(BaseModel):
        documents: list[Document]

    @telemetry_event("IngestDocuments")
    async def ingest_documents_app(self, request: IngestDocumentsRequest):
        async with manage_run(
            self.run_manager, "ingest_documents_app"
        ) as run_id:
            try:
                return await self.aingest_documents(request.documents)

            except HTTPException as he:
                raise he

            except Exception as e:
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.ingestion_pipeline.pipeline_type,
                    is_info_log=True,
                )

                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                logger.error(
                    f"ingest_documents_app(documents={request.documents}) - \n\n{str(e)})"
                )
                logger.error(
                    f"ingest_documents_app(documents={request.documents}) - \n\n{str(e)})"
                )
                raise HTTPException(status_code=500, detail=str(e))

    @syncable
    async def aupdate_documents(
        self,
        documents: list[Document],
        metadatas: Optional[list[dict]] = None,
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

        documents_info = await self.adocuments_info(
            document_ids=[doc.id for doc in documents]
        )

        for iteration, doc in enumerate(documents):
            document_info = documents_info[iteration]
            current_version = document_info.version
            old_versions.append(current_version)
            new_versions.append(increment_version(current_version))

            document_metadata = (
                metadatas[iteration] if metadatas else doc.metadata
            )
            document_metadata["title"] = (
                document_metadata.get("title", None) or doc.title
            )
            document_metadata["user_id"] = (
                str(doc.user_id) if doc.user_id else None
            )
            document_infos_modified.append(
                DocumentInfo(
                    **{
                        "document_id": doc.id,
                        "version": new_versions[-1],
                        "size_in_bytes": len(doc.data),
                        "metadata": document_metadata.copy(),
                        "title": document_metadata["title"],
                        "user_id": doc.user_id,
                        "created_at": document_info.created_at,
                        "updated_at": datetime.now(),
                    }
                )
            )

        await self.aingest_documents(documents, versions=new_versions)

        for doc, old_version in zip(documents, old_versions):
            await self.adelete(
                ["document_id", "version"], [str(doc.id), old_version]
            )

        self.providers.vector_db.upsert_documents_info(document_infos_modified)
        return {"results": "Documents updated."}

    class UpdateDocumentsRequest(BaseModel):
        documents: list[Document]

    @telemetry_event("UpdateDocuments")
    async def update_documents_app(self, request: UpdateDocumentsRequest):
        async with manage_run(
            self.run_manager, "update_documents_app"
        ) as run_id:
            try:
                return await self.aupdate_documents(request.documents)
            except Exception as e:
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.ingestion_pipeline.pipeline_type,
                    is_info_log=True,
                )
                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                logger.error(
                    f"update_documents_app(documents={request.documents}) - \n\n{str(e)})"
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def aingest_files(
        self,
        files: list[UploadFile],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[uuid.UUID]] = None,
        user_ids: Optional[list[Optional[uuid.UUID]]] = None,
        versions: Optional[list[str]] = None,
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
        if user_ids and len(user_ids) != len(files):
            raise ValueError(
                "Number of user_ids entries does not match number of files."
            )
        if len(files) == 0:
            raise HTTPException(
                status_code=400, detail="No files provided for ingestion."
            )

        try:
            documents = []
            document_infos = []
            skipped_documents = []
            processed_documents = []
            existing_document_ids = [
                str(doc_info.document_id)
                for doc_info in self.providers.vector_db.get_documents_info()
            ]

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

                document_id = (
                    generate_id_from_label(file.filename)
                    if document_ids is None
                    else document_ids[iteration]
                )
                if (
                    version is not None
                    and str(document_id) in existing_document_ids
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

                document_metadata = metadatas[iteration] if metadatas else {}
                document_title = (
                    document_metadata.get("title", None) or file.filename
                )
                document_metadata["title"] = document_title

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

            # Run the pipeline asynchronously
            await self.ingestion_pipeline.run(
                input=to_async_generator(documents),
                versions=versions,
                run_manager=self.run_manager,
            )

            if not skip_document_info:
                self.providers.vector_db.upsert_documents_info(document_infos)

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
            # Ensure all file handles are closed
            for file in files:
                file.file.close()

    @telemetry_event("IngestFiles")
    async def ingest_files_app(
        self,
        files: list[UploadFile] = File(...),
        metadatas: Optional[str] = Form(None),
        ids: Optional[str] = Form(None),
        user_ids: Optional[str] = Form(None),
    ):
        """Ingest files into the system."""
        async with manage_run(self.run_manager, "ingest_files_app") as run_id:
            try:
                if ids and ids != "null":
                    ids_list = json.loads(ids)
                    if len(ids_list) != 0:
                        try:
                            ids_list = [uuid.UUID(id) for id in ids_list]
                        except ValueError as e:
                            raise HTTPException(
                                status_code=400,
                                detail="Invalid UUID provided.",
                            ) from e
                else:
                    ids_list = None

                if user_ids and user_ids != "null":
                    user_ids_list = json.loads(user_ids)
                    if len(user_ids_list) != 0:
                        try:
                            user_ids_list = [
                                uuid.UUID(id) if id else None
                                for id in user_ids_list
                            ]
                        except ValueError as e:
                            raise HTTPException(
                                status_code=400,
                                detail="Invalid UUID provided.",
                            ) from e
                else:
                    user_ids_list = None

                # Parse metadatas if provided
                metadatas = (
                    json.loads(metadatas)
                    if metadatas and metadatas != "null"
                    else None
                )

                # Call aingest_files with the correct order of arguments
                return await self.aingest_files(
                    files=files,
                    metadatas=metadatas,
                    document_ids=ids_list,
                    user_ids=user_ids_list,
                )

            except HTTPException as he:
                raise HTTPException(he.status_code, he.detail) from he

            except Exception as e:
                logger.error(f"ingest_files() - \n\n{str(e)})")
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.ingestion_pipeline.pipeline_type,
                    is_info_log=True,
                )

                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def aupdate_files(
        self,
        files: list[UploadFile],
        ids: list[uuid.UUID],
        metadatas: Optional[list[dict]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if not files:
            raise HTTPException(
                status_code=400, detail="No files provided for update."
            )

        try:
            # Parse ids if provided
            if len(ids) != len(files):
                raise HTTPException(
                    status_code=400,
                    detail="Number of ids does not match number of files.",
                )

            # Ensure metadatas length matches files length
            if metadatas and len(metadatas) != len(files):
                raise HTTPException(
                    status_code=400,
                    detail="Number of metadata entries does not match number of files.",
                )

            # Get the current document info
            old_versions = []
            new_versions = []
            documents_info = await self.adocuments_info(document_ids=ids)
            documents_info_modified = []
            if len(documents_info) != len(files):
                raise HTTPException(
                    status_code=404,
                    detail="One or more documents was not found.",
                )
            for it, document_info in enumerate(documents_info):
                if not document_info:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Document with id {id} not found.",
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
                document_info.title = title
                document_info.metadata["title"] = title

                documents_info_modified.append(document_info)

            await self.aingest_files(
                files,
                [ele.metadata for ele in documents_info_modified],
                ids,
                versions=new_versions,
                skip_document_info=True,
            )

            # Delete the old version
            for id, old_version in zip(ids, old_versions):
                await self.adelete(
                    ["document_id", "version"], [str(id), old_version]
                )

            self.providers.vector_db.upsert_documents_info(
                documents_info_modified
            )

            return {"results": "Files updated successfully."}
        except Exception as e:
            logger.error(f"update_files(files={files}) - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            for file in files:
                file.file.close()

    class UpdateFilesRequest(BaseModel):
        files: list[UploadFile] = File(...)
        metadatas: Optional[str] = Form(None)
        ids: str = Form("")

    @telemetry_event("UpdateFiles")
    async def update_files_app(
        self,
        files: list[UploadFile] = File(...),
        metadatas: Optional[str] = Form(None),
        ids: Optional[str] = Form(None),
    ):
        async with manage_run(self.run_manager, "update_files_app") as run_id:
            try:
                # Parse metadatas if provided
                metadatas = (
                    json.loads(metadatas)
                    if metadatas and metadatas != "null"
                    else None
                )

                # Parse ids if provided
                ids_list = json.loads(ids)
                if ids_list:
                    ids_list = [uuid.UUID(id) for id in ids_list]
                if len(ids_list) != len(files):
                    raise HTTPException(
                        status_code=400,
                        detail="Number of ids does not match number of files.",
                    )
                if metadatas and len(metadatas) != len(files):
                    raise HTTPException(
                        status_code=400,
                        detail="Number of metadata entries does not match number of files.",
                    )
                return await self.aupdate_files(
                    files=files, metadatas=metadatas, ids=ids_list
                )
            except Exception as e:
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.ingestion_pipeline.pipeline_type,
                    is_info_log=True,
                )

                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def asearch(
        self,
        query: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        *args: Any,
        **kwargs: Any,
    ):
        """Search for documents based on the query."""
        async with manage_run(self.run_manager, "search_app") as run_id:
            t0 = time.time()

            search_filters = search_filters or {}
            results = await self.search_pipeline.run(
                input=to_async_generator([query]),
                search_filters=search_filters,
                search_limit=search_limit,
                run_manager=self.run_manager,
                do_hybrid_search=do_hybrid_search,
            )

            t1 = time.time()
            latency = f"{t1-t0:.2f}"

            await self.logging_connection.log(
                log_id=run_id,
                key="search_latency",
                value=latency,
                is_info_log=False,
            )

            return {"results": [result.dict() for result in results]}

    class SearchRequest(BaseModel):
        query: str
        search_filters: Optional[str] = None
        search_limit: int = 10
        do_hybrid_search: Optional[bool] = False

    @telemetry_event("Search")
    async def search_app(self, request: SearchRequest):
        async with manage_run(self.run_manager, "search_app") as run_id:
            try:
                search_filters = (
                    {}
                    if request.search_filters is None
                    or request.search_filters == "null"
                    else json.loads(request.search_filters)
                )
                return await self.asearch(
                    request.query,
                    search_filters,
                    request.search_limit,
                    request.do_hybrid_search,
                )
            except Exception as e:
                # TODO - Make this more modular
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.search_pipeline.pipeline_type,
                    is_info_log=True,
                )

                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def arag(
        self,
        message: str,
        rag_generation_config: GenerationConfig,
        search_filters: Optional[dict[str, str]] = None,
        search_limit: int = 10,
        *args,
        **kwargs,
    ):
        async with manage_run(self.run_manager, "rag_app") as run_id:
            try:
                t0 = time.time()

                if rag_generation_config.stream:
                    t1 = time.time()
                    latency = f"{t1-t0:.2f}"

                    await self.logging_connection.log(
                        log_id=run_id,
                        key="rag_generation_latency",
                        value=latency,
                        is_info_log=False,
                    )

                    async def stream_response():
                        # We must re-enter the manage_run context for the streaming pipeline
                        async with manage_run(self.run_manager, "arag"):
                            async for (
                                chunk
                            ) in await self.streaming_rag_pipeline.run(
                                input=to_async_generator([message]),
                                streaming=True,
                                search_filters=search_filters,
                                search_limit=search_limit,
                                rag_generation_config=rag_generation_config,
                                run_manager=self.run_manager,
                                *args,
                                **kwargs,
                            ):
                                yield chunk

                    return stream_response()

                if not rag_generation_config.stream:
                    results = await self.rag_pipeline.run(
                        input=to_async_generator([message]),
                        streaming=False,
                        search_filters=search_filters,
                        search_limit=search_limit,
                        rag_generation_config=rag_generation_config,
                        run_manager=self.run_manager,
                    )

                    t1 = time.time()
                    latency = f"{t1-t0:.2f}"

                    await self.logging_connection.log(
                        log_id=run_id,
                        key="rag_generation_latency",
                        value=latency,
                        is_info_log=False,
                    )

                    return results
            except Exception as e:
                logger.error(f"Pipeline error: {str(e)}")
                if "NoneType" in str(e):
                    raise HTTPException(
                        status_code=502,
                        detail="Ollama server not reachable or returned an invalid response",
                    )
                raise HTTPException(
                    status_code=500, detail="Internal Server Error"
                )

    class RAGRequest(BaseModel):
        message: str
        search_filters: Optional[str] = None
        search_limit: int = 10
        rag_generation_config: Optional[str] = None
        streaming: Optional[bool] = None

    @telemetry_event("RAG")
    async def rag_app(self, request: RAGRequest):
        async with manage_run(self.run_manager, "rag_app") as run_id:
            try:
                # Parse search filters
                search_filters = None
                if request.search_filters and request.search_filters != "null":
                    try:
                        search_filters = json.loads(request.search_filters)
                    except json.JSONDecodeError as jde:
                        logger.error(
                            f"Error parsing search filters: {str(jde)}"
                        )
                        raise HTTPException(
                            status_code=400,
                            detail=f"Error parsing search filters: {str(jde)}",
                        )

                # Parse RAG generation config
                rag_generation_config = GenerationConfig(
                    model="gpt-3.5-turbo", stream=request.streaming
                )
                if (
                    request.rag_generation_config
                    and request.rag_generation_config != "null"
                ):
                    try:
                        parsed_config = json.loads(
                            request.rag_generation_config
                        )
                        rag_generation_config = GenerationConfig(
                            **parsed_config,
                            stream=request.streaming,
                        )
                    except json.JSONDecodeError as jde:
                        logger.error(
                            f"Error parsing RAG generation config: {str(jde)}"
                        )
                        raise HTTPException(
                            status_code=400,
                            detail=f"Error parsing RAG generation config: {str(jde)}",
                        ) from jde

                # Call the async RAG method
                response = await self.arag(
                    request.message,
                    rag_generation_config,
                    search_filters,
                    request.search_limit,
                )

                if request.streaming:
                    return StreamingResponse(
                        response, media_type="application/json"
                    )
                else:
                    return {"results": response}

            except json.JSONDecodeError as jde:
                error_message = f"JSON decoding error: {str(jde)}"
                logger.error(error_message)
                raise HTTPException(status_code=400, detail=error_message)

            except HTTPException as he:
                raise he

            except Exception as e:
                # Log the error with pipeline details
                logger.error(f"Exception in RAG app: {str(e)}")
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.rag_pipeline.pipeline_type,
                    is_info_log=True,
                )
                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e))

    @syncable
    async def aevaluate(
        self,
        query: str,
        context: str,
        completion: str,
        eval_generation_config: Optional[GenerationConfig] = None,
        *args: Any,
        **kwargs: Any,
    ):
        eval_payload = R2REvalPipe.EvalPayload(
            query=query,
            context=context,
            completion=completion,
        )
        result = await self.eval_pipeline.run(
            input=to_async_generator([eval_payload]),
            run_manager=self.run_manager,
            eval_generation_config=eval_generation_config,
        )
        return {"results": result}

    class EvalRequest(BaseModel):
        query: str
        context: str
        completion: str

    @telemetry_event("Evaluate")
    async def evaluate_app(self, request: EvalRequest):
        async with manage_run(self.run_manager, "evaluate_app") as run_id:
            try:
                return await self.aevaluate(
                    query=request.query,
                    context=request.context,
                    completion=request.completion,
                )
            except Exception as e:
                await self.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=self.eval_pipeline.pipeline_type,
                    is_info_log=True,
                )

                await self.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def adelete(
        self,
        keys: list[str],
        values: list[Union[bool, int, str]],
        *args: Any,
        **kwargs: Any,
    ):
        ids = self.providers.vector_db.delete_by_metadata(keys, values)
        self.providers.vector_db.delete_documents_info(ids)

        return {"results": "Entries deleted successfully."}

    class DeleteRequest(BaseModel):
        keys: list[str]
        values: list[Union[bool, int, str]]

    @telemetry_event("Delete")
    async def delete_app(self, request: DeleteRequest = Body(...)):
        try:
            return await self.adelete(request.keys, request.values)
        except Exception as e:
            logger.error(
                f":delete: [Error](key={request.keys}, value={request.values}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def alogs(
        self,
        log_type_filter: Optional[str] = None,
        max_runs_requested: int = 100,
        *args: Any,
        **kwargs: Any,
    ):
        if self.logging_connection is None:
            raise HTTPException(
                status_code=404, detail="Logging provider not found."
            )
        if (
            self.config.app.get("max_logs_per_request", 100)
            > max_runs_requested
        ):
            raise HTTPException(
                status_code=400,
                detail="Max runs requested exceeds the limit.",
            )

        run_info = await self.logging_connection.get_run_info(
            limit=max_runs_requested,
            log_type_filter=log_type_filter,
        )
        run_ids = [run.run_id for run in run_info]
        if len(run_ids) == 0:
            return {"results": []}
        logs = await self.logging_connection.get_logs(run_ids)
        # Aggregate logs by run_id and include run_type
        aggregated_logs = []

        for run in run_info:
            run_logs = [log for log in logs if log["log_id"] == run.run_id]
            entries = [
                {"key": log["key"], "value": log["value"]} for log in run_logs
            ][
                ::-1
            ]  # Reverse order so that earliest logged values appear first.
            aggregated_logs.append(
                {
                    "run_id": run.run_id,
                    "run_type": run.log_type,
                    "entries": entries,
                }
            )

        return {"results": aggregated_logs}

    @telemetry_event("Logs")
    async def logs_app(
        self,
        log_type_filter: Optional[str] = Query(None),
        max_runs_requested: int = Query(100),
    ):
        try:
            return await self.alogs(log_type_filter, max_runs_requested)
        except Exception as e:
            logger.error(f":logs: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def aanalytics(
        self,
        filter_criteria: FilterCriteria,
        analysis_types: AnalysisTypes,
        *args: Any,
        **kwargs: Any,
    ):
        run_info = await self.logging_connection.get_run_info(limit=100)
        run_ids = [info.run_id for info in run_info]

        if not run_ids:
            return {
                "results": {
                    "analytics_data": "No logs found.",
                    "filtered_logs": {},
                }
            }

        logs = await self.logging_connection.get_logs(run_ids=run_ids)

        filters = {}
        if filter_criteria.filters:
            for key, value in filter_criteria.filters.items():
                filters[key] = lambda log, value=value: (
                    any(
                        entry.get("key") == value
                        for entry in log.get("entries", [])
                    )
                    if "entries" in log
                    else log.get("key") == value
                )

        log_processor = LogProcessor(filters)
        for log in logs:
            if "entries" in log and isinstance(log["entries"], list):
                log_processor.process_log(log)
            elif "key" in log:
                log_processor.process_log(log)
            else:
                logger.warning(
                    f"Skipping log due to missing or malformed 'entries': {log}"
                )

        filtered_logs = dict(log_processor.populations.items())

        results = {"filtered_logs": filtered_logs}

        if analysis_types and analysis_types.analysis_types:
            for (
                filter_key,
                analysis_config,
            ) in analysis_types.analysis_types.items():
                if filter_key in filtered_logs:
                    analysis_type = analysis_config[0]
                    if analysis_type == "bar_chart":
                        extract_key = analysis_config[1]
                        results[filter_key] = (
                            AnalysisTypes.generate_bar_chart_data(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "basic_statistics":
                        extract_key = analysis_config[1]
                        results[filter_key] = (
                            AnalysisTypes.calculate_basic_statistics(
                                filtered_logs[filter_key], extract_key
                            )
                        )
                    elif analysis_type == "percentile":
                        extract_key = analysis_config[1]
                        percentile = int(analysis_config[2])
                        results[filter_key] = (
                            AnalysisTypes.calculate_percentile(
                                filtered_logs[filter_key],
                                extract_key,
                                percentile,
                            )
                        )
                    else:
                        logger.warning(
                            f"Unknown analysis type for filter key '{filter_key}': {analysis_type}"
                        )

        return {"results": results}

    @telemetry_event("Analytics")
    async def analytics_app(
        self,
        filter_criteria: FilterCriteria = Body(...),
        analysis_types: AnalysisTypes = Body(...),
    ):
        async with manage_run(self.run_manager, "analytics_app") as run_id:
            try:
                return await self.aanalytics(filter_criteria, analysis_types)
            except Exception as e:
                await self.run_manager.log_run_info(
                    "error", str(e), is_info_log=False
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def aapp_settings(self, *args: Any, **kwargs: Any):
        # config_data = self.config.app  # Assuming this holds your config.json data
        prompts = self.providers.prompt.get_all_prompts()
        return {
            "results": {
                "config": self.config.to_json(),
                "prompts": {
                    name: prompt.dict() for name, prompt in prompts.items()
                },
            }
        }

    @telemetry_event("AppSettings")
    async def app_settings_app(self):
        """Return the config.json and all prompts."""
        try:
            return await self.aapp_settings()
        except Exception as e:
            logger.error(f"app_settings_app() - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def ausers_stats(self, user_ids: Optional[list[uuid.UUID]] = None):
        return self.providers.vector_db.get_users_stats(
            [str(ele) for ele in user_ids]
        )

    @telemetry_event("UsersStats")
    async def users_stats_app(
        self, user_ids: Optional[list[uuid.UUID]] = Query(None)
    ):
        try:
            users_stats = await self.ausers_stats(user_ids)
            return {"results": users_stats}
        except Exception as e:
            logger.error(
                f"users_stats_app(user_ids={user_ids}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def adocuments_info(
        self,
        document_ids: Optional[list[uuid.UUID]] = None,
        user_ids: Optional[list[uuid.UUID]] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return self.providers.vector_db.get_documents_info(
            filter_document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            filter_user_ids=(
                [str(ele) for ele in user_ids] if user_ids else None
            ),
        )

    @telemetry_event("DocumentsInfo")
    async def documents_info_app(
        self,
        document_ids: Optional[list[str]] = Query(None),
        user_ids: Optional[list[str]] = Query(None),
    ):
        try:
            documents_info = await self.adocuments_info(
                document_id=document_ids, user_id=user_ids
            )
            return {"results": documents_info}
        except Exception as e:
            logger.error(
                f"documents_info_app(document_ids={document_ids}, user_ids={user_ids}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @syncable
    async def adocument_chunks(self, document_id: str) -> list[str]:
        return self.providers.vector_db.get_document_chunks(document_id)

    @telemetry_event("DocumentChunks")
    async def document_chunks_app(self, document_id: str):
        try:
            chunks = await self.adocument_chunks(document_id)
            return {"results": chunks}
        except Exception as e:
            logger.error(
                f"get_document_chunks_app(document_id={document_id}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @telemetry_event("OpenAPI")
    def openapi_spec_app(self):
        from fastapi.openapi.utils import get_openapi

        return {
            "results": get_openapi(
                title="R2R Application API",
                version="1.0.0",
                routes=self.app.routes,
            )
        }

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "Please install uvicorn using 'pip install uvicorn'"
            )

        uvicorn.run(self.app, host=host, port=port)

    def _apply_cors(self):
        # CORS setup
        origins = [
            "*",  # TODO - Change this to the actual frontend URL
            "http://localhost:3000",
            "http://localhost:8000",
        ]

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,  # Allows specified origins
            allow_credentials=True,
            allow_methods=["*"],  # Allows all methods
            allow_headers=["*"],  # Allows all headers
        )
