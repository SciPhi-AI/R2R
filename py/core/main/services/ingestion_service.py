import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, Sequence, Union
from uuid import UUID

from core.base import (
    Document,
    DocumentChunk,
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    R2RException,
    RawChunk,
    RunManager,
    Vector,
    VectorEntry,
    VectorType,
    decrement_version,
)
from core.base.abstractions import (
    ChunkEnrichmentSettings,
    ChunkEnrichmentStrategy,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)
from core.base.api.models import UserResponse
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()
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
        logging_connection: SqlitePersistentLoggingProvider,
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
        document_id: UUID,
        size_in_bytes,
        metadata: Optional[dict] = None,
        version: Optional[str] = None,
        is_update: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        try:
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
            document_info = self._create_document_info_from_file(
                document_id,
                user,
                file_data["filename"],
                metadata,
                version,
                size_in_bytes,
            )

            existing_document_info = (
                await self.providers.database.get_documents_overview(
                    filter_user_ids=[user.id],
                    filter_document_ids=[document_id],
                )
            )["results"]

            if not is_update and len(existing_document_info) > 0:
                existing_doc = existing_document_info[0]
                if (
                    existing_doc.version >= version
                    and existing_doc.ingestion_status
                    == IngestionStatus.SUCCESS
                ):
                    raise R2RException(
                        status_code=409,
                        message=f"Document {document_id} already exists. Increment the version to overwrite existing document. Otherwise, submit a POST request to `/documents/{document_id}` to update the existing version.",
                    )
                elif existing_doc.ingestion_status != IngestionStatus.FAILED:
                    raise R2RException(
                        status_code=409,
                        message=f"Document {document_id} is currently ingesting.",
                    )

            await self.providers.database.upsert_documents_overview(
                document_info
            )

            return {
                "info": document_info,
            }
        except R2RException as e:
            logger.error(f"R2RException in ingest_file_ingress: {str(e)}")
            raise
        except Exception as e:
            raise R2RException(
                status_code=500, message=f"Error during ingestion: {str(e)}"
            )

    def _create_document_info_from_file(
        self,
        document_id: UUID,
        user: UserResponse,
        file_name: str,
        metadata: dict,
        version: str,
        size_in_bytes: int,
    ) -> DocumentInfo:
        file_extension = (
            file_name.split(".")[-1].lower() if file_name != "N/A" else "txt"
        )
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
            document_type=DocumentType[file_extension.upper()],
            title=(
                metadata.get("title", file_name.split("/")[-1])
                if file_name != "N/A"
                else "N/A"
            ),
            metadata=metadata,
            version=version,
            size_in_bytes=size_in_bytes,
            ingestion_status=IngestionStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def _create_document_info_from_chunks(
        self,
        document_id: UUID,
        user: UserResponse,
        chunks: list[RawChunk],
        metadata: dict,
        version: str,
    ) -> DocumentInfo:
        metadata = metadata or {}
        metadata["version"] = version

        return DocumentInfo(
            id=document_id,
            user_id=user.id,
            collection_ids=metadata.get("collection_ids", []),
            document_type=DocumentType.TXT,
            title=metadata.get("title", f"Ingested Chunks - {document_id}"),
            metadata=metadata,
            version=version,
            size_in_bytes=sum(
                len(chunk.text.encode("utf-8")) for chunk in chunks
            ),
            ingestion_status=IngestionStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def parse_file(
        self, document_info: DocumentInfo, ingestion_config: dict
    ) -> AsyncGenerator[DocumentChunk, None]:
        return await self.pipes.parsing_pipe.run(
            input=self.pipes.parsing_pipe.Input(
                message=Document(
                    id=document_info.id,
                    collection_ids=document_info.collection_ids,
                    user_id=document_info.user_id,
                    metadata={
                        "document_type": document_info.document_type.value,
                        **document_info.metadata,
                    },
                    document_type=document_info.document_type,
                )
            ),
            state=None,
            run_manager=self.run_manager,
            ingestion_config=ingestion_config,
        )

    async def embed_document(
        self,
        chunked_documents: list[dict],
    ) -> AsyncGenerator[VectorEntry, None]:
        return await self.pipes.embedding_pipe.run(
            input=self.pipes.embedding_pipe.Input(
                message=[
                    DocumentChunk.from_dict(chunk)
                    for chunk in chunked_documents
                ]
            ),
            state=None,
            run_manager=self.run_manager,
        )

    async def store_embeddings(
        self,
        embeddings: Sequence[Union[dict, VectorEntry]],
    ) -> AsyncGenerator[str, None]:
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
            state=None,
            run_manager=self.run_manager,
        )

    async def finalize_ingestion(
        self,
        document_info: DocumentInfo,
        is_update: bool = False,
    ) -> None:
        if is_update:
            await self.providers.database.delete(
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
            await self.providers.database.upsert_documents_overview(
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

    @telemetry_event("IngestChunks")
    async def ingest_chunks_ingress(
        self,
        document_id: UUID,
        metadata: Optional[dict],
        chunks: list[RawChunk],
        user: UserResponse,
        *args: Any,
        **kwargs: Any,
    ) -> DocumentInfo:
        if not chunks:
            raise R2RException(
                status_code=400, message="No chunks provided for ingestion."
            )

        metadata = metadata or {}
        version = STARTING_VERSION

        document_info = self._create_document_info_from_chunks(
            document_id,
            user,
            chunks,
            metadata,
            version,
        )

        existing_document_info = (
            await self.providers.database.get_documents_overview(
                filter_user_ids=[user.id],
                filter_document_ids=[document_id],
            )
        )["results"]

        if len(existing_document_info) > 0:
            existing_doc = existing_document_info[0]
            if existing_doc.ingestion_status != IngestionStatus.FAILED:
                raise R2RException(
                    status_code=409,
                    message=f"Document {document_id} was already ingested and is not in a failed state.",
                )

        await self.providers.database.upsert_documents_overview(document_info)

        return document_info

    @telemetry_event("UpdateChunk")
    async def update_chunk_ingress(
        self,
        document_id: UUID,
        chunk_id: UUID,
        text: str,
        user: UserResponse,
        metadata: Optional[dict] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        # Verify chunk exists and user has access
        existing_chunks = await self.providers.database.list_document_chunks(
            document_id=document_id, limit=1
        )

        if not existing_chunks["results"]:
            raise R2RException(
                status_code=404,
                message=f"Chunk with chunk_id {chunk_id} not found.",
            )

        existing_chunk = await self.providers.database.get_chunk(chunk_id)
        if not existing_chunk:
            raise R2RException(
                status_code=404,
                message=f"Chunk with id {chunk_id} not found",
            )

        if (
            str(existing_chunk["user_id"]) != str(user.id)
            and not user.is_superuser
        ):
            raise R2RException(
                status_code=403,
                message="You don't have permission to modify this chunk.",
            )

        # Handle metadata merging
        if metadata is not None:
            merged_metadata = {
                **existing_chunk["metadata"],
                **metadata,
            }
        else:
            merged_metadata = existing_chunk["metadata"]

        # Create updated extraction
        extraction_data = {
            "id": chunk_id,
            "document_id": document_id,
            "collection_ids": kwargs.get(
                "collection_ids", existing_chunk["collection_ids"]
            ),
            "user_id": existing_chunk["user_id"],
            "data": text or existing_chunk["text"],
            "metadata": merged_metadata,
        }

        extraction = DocumentChunk(**extraction_data).model_dump()

        embedding_generator = await self.embed_document([extraction])
        embeddings = [
            embedding.model_dump() async for embedding in embedding_generator
        ]

        storage_generator = await self.store_embeddings(embeddings)
        async for _ in storage_generator:
            pass

        return extraction

    async def _get_enriched_chunk_text(
        self,
        chunk_idx: int,
        chunk: dict,
        document_id: UUID,
        chunk_enrichment_settings: ChunkEnrichmentSettings,
        list_document_chunks: list[dict],
        document_chunks_dict: dict,
    ) -> VectorEntry:
        # get chunks in context
        context_chunk_ids: list[UUID] = []
        for enrichment_strategy in chunk_enrichment_settings.strategies:
            if enrichment_strategy == ChunkEnrichmentStrategy.NEIGHBORHOOD:
                context_chunk_ids.extend(
                    list_document_chunks[chunk_idx - prev]["chunk_id"]
                    for prev in range(
                        1, chunk_enrichment_settings.backward_chunks + 1
                    )
                    if chunk_idx - prev >= 0
                )
                context_chunk_ids.extend(
                    list_document_chunks[chunk_idx + next]["chunk_id"]
                    for next in range(
                        1, chunk_enrichment_settings.forward_chunks + 1
                    )
                    if chunk_idx + next < len(list_document_chunks)
                )
            elif enrichment_strategy == ChunkEnrichmentStrategy.SEMANTIC:
                semantic_neighbors = await self.providers.database.get_semantic_neighbors(
                    document_id=document_id,
                    chunk_id=chunk["chunk_id"],
                    limit=chunk_enrichment_settings.semantic_neighbors,
                    similarity_threshold=chunk_enrichment_settings.semantic_similarity_threshold,
                )
                context_chunk_ids.extend(
                    neighbor["chunk_id"] for neighbor in semantic_neighbors
                )

        context_chunk_ids = list(set(context_chunk_ids))

        context_chunk_texts = [
            (
                document_chunks_dict[context_chunk_id]["text"],
                document_chunks_dict[context_chunk_id]["metadata"][
                    "chunk_order"
                ],
            )
            for context_chunk_id in context_chunk_ids
        ]

        # sort by chunk_order
        context_chunk_texts.sort(key=lambda x: x[1])

        # enrich chunk
        try:
            updated_chunk_text = (
                (
                    await self.providers.llm.aget_completion(
                        messages=await self.providers.database.prompt_handler.get_message_payload(
                            task_prompt_name="chunk_enrichment",
                            task_inputs={
                                "context_chunks": "\n".join(
                                    text for text, _ in context_chunk_texts
                                ),
                                "chunk": chunk["text"],
                            },
                        ),
                        generation_config=chunk_enrichment_settings.generation_config,
                    )
                )
                .choices[0]
                .message.content
            )

        except Exception as e:
            updated_chunk_text = chunk["text"]
            chunk["metadata"]["chunk_enrichment_status"] = "failed"
        else:
            if not updated_chunk_text:
                updated_chunk_text = chunk["text"]
                chunk["metadata"]["chunk_enrichment_status"] = "failed"
            else:
                chunk["metadata"]["chunk_enrichment_status"] = "success"

        data = await self.providers.embedding.async_get_embedding(
            updated_chunk_text or chunk["text"]
        )

        chunk["metadata"]["original_text"] = chunk["text"]

        return VectorEntry(
            chunk_id=uuid.uuid5(uuid.NAMESPACE_DNS, str(chunk["chunk_id"])),
            vector=Vector(data=data, type=VectorType.FIXED, length=len(data)),
            document_id=document_id,
            user_id=chunk["user_id"],
            collection_ids=chunk["collection_ids"],
            text=updated_chunk_text or chunk["text"],
            metadata=chunk["metadata"],
        )

    async def chunk_enrichment(self, document_id: UUID) -> int:
        # just call the pipe on every chunk of the document

        # TODO: Why is the config not recognized as an ingestionconfig but as a providerconfig?
        chunk_enrichment_settings = (
            self.providers.ingestion.config.chunk_enrichment_settings  # type: ignore
        )
        # get all list_document_chunks
        list_document_chunks = (
            await self.providers.database.list_document_chunks(
                document_id=document_id,
            )
        )["results"]

        new_vector_entries = []
        document_chunks_dict = {
            chunk["chunk_id"]: chunk for chunk in list_document_chunks
        }

        tasks = []
        total_completed = 0
        for chunk_idx, chunk in enumerate(list_document_chunks):
            tasks.append(
                self._get_enriched_chunk_text(
                    chunk_idx,
                    chunk,
                    document_id,
                    chunk_enrichment_settings,
                    list_document_chunks,
                    document_chunks_dict,
                )
            )

            if len(tasks) == 128:
                new_vector_entries.extend(await asyncio.gather(*tasks))
                total_completed += 128
                logger.info(
                    f"Completed {total_completed} out of {len(list_document_chunks)} chunks for document {document_id}"
                )
                tasks = []

        new_vector_entries.extend(await asyncio.gather(*tasks))
        logger.info(
            f"Completed enrichment of {len(list_document_chunks)} chunks for document {document_id}"
        )

        # delete old chunks from vector db
        await self.providers.database.delete(
            filters={
                "document_id": document_id,
            },
        )

        # embed and store the enriched chunk
        await self.providers.database.upsert_entries(new_vector_entries)

        return len(new_vector_entries)

    # TODO - This should return a typed object
    async def list_chunks(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        include_vectors: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        return await self.providers.database.list_chunks()

    # TODO - This should return a typed object
    async def get_chunk(
        self,
        # document_id: UUID,
        chunk_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> dict:
        return await self.providers.database.get_chunk(chunk_id)


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
    def _parse_chunk_enrichment_settings(
        chunk_enrichment_settings: dict,
    ) -> ChunkEnrichmentSettings:
        if isinstance(chunk_enrichment_settings, str):
            try:
                chunk_enrichment_settings = json.loads(
                    chunk_enrichment_settings
                )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid chunk enrichment settings format: {chunk_enrichment_settings}"
                ) from e
        return ChunkEnrichmentSettings.from_dict(chunk_enrichment_settings)

    @staticmethod
    def parse_ingest_file_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "metadata": data["metadata"],
            "document_id": (
                UUID(data["document_id"]) if data["document_id"] else None
            ),
            "version": data.get("version"),
            "ingestion_config": data["ingestion_config"] or {},
            "is_update": data.get("is_update", False),
            "file_data": data["file_data"],
            "size_in_bytes": data["size_in_bytes"],
        }

    @staticmethod
    def parse_ingest_chunks_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "metadata": data["metadata"],
            "document_id": data["document_id"],
            "chunks": [RawChunk.from_dict(chunk) for chunk in data["chunks"]],
        }

    @staticmethod
    def parse_update_chunk_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_id": UUID(data["document_id"]),
            "chunk_id": UUID(data["chunk_id"]),
            "text": data["text"],
            "metadata": data.get("metadata"),
            "collection_ids": data.get("collection_ids", []),
        }

    @staticmethod
    def parse_update_files_input(data: dict) -> dict:
        return {
            "user": IngestionServiceAdapter._parse_user_data(data["user"]),
            "document_ids": [UUID(doc_id) for doc_id in data["document_ids"]],
            "metadatas": data["metadatas"],
            "ingestion_config": data["ingestion_config"],
            "file_sizes_in_bytes": data["file_sizes_in_bytes"],
            "file_datas": data["file_datas"],
        }

    @staticmethod
    def parse_create_vector_index_input(data: dict) -> dict:
        return {
            "table_name": VectorTableName(data["table_name"]),
            "index_method": IndexMethod(data["index_method"]),
            "index_measure": IndexMeasure(data["index_measure"]),
            "index_name": data["index_name"],
            "index_column": data["index_column"],
            "index_arguments": data["index_arguments"],
            "concurrently": data["concurrently"],
        }

    @staticmethod
    def parse_list_vector_indices_input(input_data: dict) -> dict:
        return {"table_name": input_data["table_name"]}

    @staticmethod
    def parse_delete_vector_index_input(input_data: dict) -> dict:
        return {
            "index_name": input_data["index_name"],
            "table_name": input_data.get("table_name"),
            "concurrently": input_data.get("concurrently", True),
        }

    @staticmethod
    def parse_select_vector_index_input(input_data: dict) -> dict:
        return {
            "index_name": input_data["index_name"],
            "table_name": input_data.get("table_name"),
        }
