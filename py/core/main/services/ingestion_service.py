import base64
import functools
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID

from core.base import (
    Document,
    DocumentExtraction,
    DocumentFragment,
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    R2RDocumentProcessingError,
    R2RException,
    RunLoggingSingleton,
    RunManager,
    VectorEntry,
    decrement_version,
    generate_user_document_id,
)
from core.base.providers import ChunkingConfig
from core.telemetry.telemetry_decorator import telemetry_event

from ...base.api.models.auth.responses import UserResponse
from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)
MB_CONVERSION_FACTOR = 1024 * 1024
STARTING_VERSION = "v0"
MAX_FILES_PER_INGESTION = 100
OVERVIEW_FETCH_PAGE_SIZE = 1_000


def ingestion_step(step_name: str) -> Callable[..., Any]:
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Any:
        @functools.wraps(func)
        async def wrapper(self, document_info: DocumentInfo, *args, **kwargs):
            document_info.ingestion_status = getattr(
                IngestionStatus, step_name.upper()
            )
            self.providers.database.relational.upsert_documents_overview(
                document_info
            )

            try:
                result_gen = await func(self, document_info, *args, **kwargs)
                return await self._collect_results(result_gen)
            except R2RDocumentProcessingError as e:
                await self.mark_document_as_failed(document_info, e)
                raise
            except Exception as e:
                error = R2RDocumentProcessingError(
                    document_id=document_info.id,
                    error_message=f"Error in {step_name} step: {str(e)}",
                )
                await self.mark_document_as_failed(document_info, error)
                raise error

        return wrapper

    return decorator


class IngestionService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ) -> None:
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        self.providers.database.relational.store_file(
            document_id, file_name, file_content, file_type
        )

    @telemetry_event("IngestFile")
    async def ingest_file_ingress(
        self,
        file_data: dict,
        user: UserResponse,
        metadata: Optional[dict] = None,
        document_id: Optional[UUID] = None,
        version: Optional[str] = None,
        is_update: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        if not file_data:
            raise R2RException(
                status_code=400, message="No files provided for ingestion."
            )

        if not file_data.get("filename"):
            raise R2RException(
                status_code=400, message="File name not provided."
            )

        metadata = metadata or {}

        document_id = document_id or generate_user_document_id(
            file_data["filename"], user.id
        )
        file_content = BytesIO(base64.b64decode(file_data["content"]))

        self.store_file(
            document_id,
            file_data["filename"],
            file_content,
            file_data["content_type"],
        )

        version = version or STARTING_VERSION
        document_info = self._create_document_info(
            document_id,
            user,
            file_data["filename"],
            metadata,
            version,
            len(file_content.getvalue()),
        )

        if existing_document_info := self.providers.database.relational.get_documents_overview(
            filter_user_ids=[user.id],
            filter_document_ids=[document_id],
        ):
            existing_doc = existing_document_info[0]
            if is_update:
                if (
                    existing_doc.version >= version
                    and existing_doc.ingestion_status == "success"
                ):
                    raise R2RException(
                        status_code=409,
                        message=f"Must increment version number before attempting to overwrite document {document_id}.",
                    )
            elif existing_doc.ingestion_status != "failure":
                raise R2RException(
                    status_code=409,
                    message=f"Document {document_id} was already ingested and is not in a failed state.",
                )

        self.providers.database.relational.upsert_documents_overview(
            document_info
        )

        return {
            "info": document_info,
        }

    def _create_document_info(
        self,
        document_id: UUID,
        user: UserResponse,
        file_name: str,
        metadata: dict,
        version: str,
        file_size: int,
    ) -> DocumentInfo:
        file_extension = file_name.split(".")[-1].lower()
        if file_extension.upper() not in DocumentType.__members__:
            raise R2RException(
                status_code=415,
                message=f"'{file_extension}' is not a valid DocumentType.",
            )

        metadata = metadata or {}
        metadata["title"] = metadata.get("title") or file_name.split("/")[-1]
        metadata["version"] = version

        return DocumentInfo(
            id=document_id,
            user_id=user.id,
            group_ids=metadata.get("group_ids", []),
            type=DocumentType[file_extension.upper()],
            title=metadata["title"],
            metadata=metadata,
            version=version,
            size_in_bytes=file_size,
            ingestion_status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @ingestion_step("parsing")
    async def parse_file(
        self,
        document_info: DocumentInfo,
    ) -> list[DocumentFragment]:
        file_name, file_wrapper, file_size = self.providers.file.retrieve_file(
            document_info.id
        )

        with file_wrapper as file_content_stream:
            return await self.pipes.parsing_pipe.run(
                input=self.pipes.parsing_pipe.Input(
                    message=Document(
                        id=document_info.id,
                        group_ids=document_info.group_ids,
                        user_id=document_info.user_id,
                        type=document_info.type,
                        metadata={
                            "file_name": file_name,
                            "file_size": file_size,
                            "document_type": document_info.type.value,
                            **document_info.metadata,
                        },
                    )
                ),
                run_manager=self.run_manager,
            )

    @ingestion_step("chunking")
    async def chunk_document(
        self,
        document_info: DocumentInfo,
        parsed_documents: list[dict],
        chunking_config: Optional[ChunkingConfig] = None,
    ) -> list[DocumentFragment]:

        return await self.pipes.chunking_pipe.run(
            input=self.pipes.chunking_pipe.Input(
                message=[
                    DocumentExtraction.from_dict(chunk)
                    for chunk in parsed_documents
                ]
            ),
            run_manager=self.run_manager,
            chunking_config=chunking_config,
        )

    @ingestion_step("embedding")
    async def embed_document(
        self,
        document_info: DocumentInfo,
        chunked_documents: list[dict],
    ) -> list[str]:
        return await self.pipes.embedding_pipe.run(
            input=self.pipes.embedding_pipe.Input(
                message=[
                    DocumentFragment.from_dict(chunk)
                    for chunk in chunked_documents
                ]
            ),
            run_manager=self.run_manager,
        )

    @ingestion_step("storing")
    async def store_embeddings(
        self,
        document_info: DocumentInfo,
        embeddings: list[dict],
    ) -> list[str]:
        return await self.pipes.vector_storage_pipe.run(
            input=self.pipes.vector_storage_pipe.Input(
                message=[
                    VectorEntry.from_dict(embedding)
                    for embedding in embeddings
                ]
            ),
            run_manager=self.run_manager,
        )

    @ingestion_step("success")
    async def finalize_ingestion(
        self,
        document_info: DocumentInfo,
        is_update: bool = False,
    ) -> None:
        if is_update:
            self.providers.database.vector.delete(
                filters={
                    "$and": [
                        {"document_id": {"$eq": document_info.id}},
                        {
                            "version": {
                                "$eq": decrement_version(document_info.version)
                            }
                        },
                    ]
                }
            )

        async def empty_generator():
            yield document_info

        return empty_generator()

    async def _process_ingestion_results(
        self,
        ingestion_results: dict,
        document_infos: list[DocumentInfo],
        skipped_documents: list[dict[str, str]],
    ) -> dict:
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

    async def mark_document_as_failed(
        self,
        document_info: DocumentInfo,
        error: R2RDocumentProcessingError,
    ) -> None:
        document_info.ingestion_status = "failure"
        document_info.metadata["error"] = error.message
        self.providers.database.relational.upsert_documents_overview(
            document_info
        )

    async def _collect_results(self, result_gen: Any) -> list[dict]:
        results = []
        async for res in result_gen:
            results.append(res.model_dump_json())
        return results


class IngestionServiceAdapter:
    @staticmethod
    def _parse_user_data(user_data) -> UserResponse:
        if isinstance(user_data, str):
            try:
                user_data = json.loads(user_data)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid user data format: {user_data}"
                ) from e
        return UserResponse.from_dict(user_data)

    @staticmethod
    def parse_ingest_file_input(data: dict) -> dict:
        return {
            "file_data": data["file_data"],
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "metadata": data["metadata"],
            "document_id": (
                UUID(data["document_id"]) if data["document_id"] else None
            ),
            "version": data.get("version"),
            "chunking_config": (
                ChunkingConfig.from_dict(data["chunking_config"])
                if data["chunking_config"]
                else None
            ),
            "is_update": data.get("is_update", False),
        }

    @staticmethod
    def parse_update_files_input(data: dict) -> dict:
        return {
            "file_datas": data["file_datas"],
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_ids": [UUID(doc_id) for doc_id in data["document_ids"]],
            "metadatas": data["metadatas"],
            "chunking_config": (
                ChunkingConfig.from_dict(data["chunking_config"])
                if data["chunking_config"]
                else None
            ),
        }
