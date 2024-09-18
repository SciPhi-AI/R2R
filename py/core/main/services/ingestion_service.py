import json
import logging
from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from core.base import (
    Document,
    DocumentExtraction,
    DocumentFragment,
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    R2RException,
    RunLoggingSingleton,
    RunManager,
    VectorEntry,
    decrement_version,
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

    @telemetry_event("IngestFile")
    async def ingest_file_ingress(
        self,
        file_data: dict,
        user: UserResponse,
        metadata: Optional[dict] = None,
        document_id: Optional[UUID] = None,
        version: Optional[str] = None,
        is_update: bool = False,
        size_in_bytes: Optional[int] = None,
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

        version = version or STARTING_VERSION
        document_info = self._create_document_info(
            document_id,
            user,
            file_data["filename"],
            metadata,
            version,
            size_in_bytes,
        )

        if existing_document_info := await self.providers.database.relational.get_documents_overview(
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

        await self.providers.database.relational.upsert_documents_overview(
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
        size_in_bytes: int,
    ) -> DocumentInfo:
        file_extension = file_name.split(".")[-1].lower()
        if file_extension.upper() not in DocumentType.__members__:
            raise R2RException(
                status_code=415,
                message=f"'{file_extension}' is not a valid DocumentType.",
            )

        metadata = metadata or {}
        metadata["version"] = version

        return DocumentInfo(
            id=document_id,
            user_id=user.id,
            collection_ids=metadata.get("collection_ids", []),
            type=DocumentType[file_extension.upper()],
            title=metadata.get("title", file_name.split("/")[-1]),
            metadata=metadata,
            version=version,
            size_in_bytes=size_in_bytes,
            ingestion_status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def parse_file(
        self,
        document_info: DocumentInfo,
    ) -> list[DocumentFragment]:
        file_name, file_wrapper, size_in_bytes = (
            await self.providers.file.retrieve_file(document_info.id)
        )

        with file_wrapper as file_content_stream:
            return await self.pipes.parsing_pipe.run(
                input=self.pipes.parsing_pipe.Input(
                    message=Document(
                        id=document_info.id,
                        collection_ids=document_info.collection_ids,
                        user_id=document_info.user_id,
                        type=document_info.type,
                        metadata={
                            "document_type": document_info.type.value,
                            **document_info.metadata,
                        },
                    )
                ),
                run_manager=self.run_manager,
            )

    async def chunk_document(
        self,
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

    async def embed_document(
        self,
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

    async def store_embeddings(
        self,
        embeddings: list[Union[dict, VectorEntry]],
    ) -> list[str]:
        vector_entries = [
            (
                embedding
                if isinstance(embedding, VectorEntry)
                else VectorEntry.from_dict(embedding)
            )
            for embedding in embeddings
        ]

        return await self.pipes.vector_storage_pipe.run(
            input=self.pipes.vector_storage_pipe.Input(message=vector_entries),
            run_manager=self.run_manager,
        )

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

    async def update_document_status(
        self,
        document_info: DocumentInfo,
        status: IngestionStatus,
    ) -> None:
        document_info.ingestion_status = status
        await self._update_document_status_in_db(document_info)

    async def _update_document_status_in_db(self, document_info: DocumentInfo):
        try:
            await self.providers.database.relational.upsert_documents_overview(
                document_info
            )
        except Exception as e:
            logger.error(
                f"Failed to update document status: {document_info.id}. Error: {str(e)}"
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
            "file_data": data["file_data"],
            "size_in_bytes": data["size_in_bytes"],
        }

    @staticmethod
    def parse_update_files_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_ids": [UUID(doc_id) for doc_id in data["document_ids"]],
            "metadatas": data["metadatas"],
            "chunking_config": (
                ChunkingConfig.from_dict(data["chunking_config"])
                if data["chunking_config"]
                else None
            ),
            "file_sizes_in_bytes": data["file_sizes_in_bytes"],
            "file_datas": data["file_datas"],
        }
